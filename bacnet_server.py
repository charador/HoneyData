# Copyright (C) 2015  Peter Sooky <xsooky00@stud.fit.vubtr.cz>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# Author: Peter Sooky <xsooky00@stud.fit.vubtr.cz>
# Brno University of Technology, Faculty of Information Technology

import logging
import socket
from lxml import etree

from gevent.server import DatagramServer
from bacpypes.service.device import LocalDeviceObject
from bacpypes.apdu import APDU, apdu_types
from bacpypes.pdu import PDU
from bacpypes.errors import DecodingError
from bacpypes.bvll import BVLPDU, bvl_pdu_types, ForwardedNPDU, \
    DistributeBroadcastToNetwork, OriginalUnicastNPDU, OriginalBroadcastNPDU
from bacpypes.npdu import NPDU, npdu_types

import conpot.core as conpot_core
from conpot.protocols.bacnet.bacnet_app import BACnetApp

logger = logging.getLogger(__name__)


class BacnetServer(object):
    def __init__(self, template, template_directory, args):
        self.dom = etree.parse(template)
        databus = conpot_core.get_databus()
        device_info_root = self.dom.xpath('//bacnet/device_info')[0]
        logger.info('deviceinforoot is %s', device_info_root)
        name_key = databus.get_value(device_info_root.xpath('./device_name/text()')[0])
        id_key = device_info_root.xpath('./device_identifier/text()')[0]
        location = device_info_root.xpath('./location/text()')[0]
        vendor_name_key = device_info_root.xpath('./vendor_name/text()')[0]
        vendor_identifier_key = device_info_root.xpath(
            './vendor_identifier/text()')[0]
        apdu_length_key = device_info_root.xpath(
            './max_apdu_length_accepted/text()')[0]
        segmentation_key = device_info_root.xpath(
            './segmentation_supported/text()')[0]
        application_software_version = device_info_root.xpath(
            './application_software_version/text()')[0]
        model_name = device_info_root.xpath('./model_name/text()')[0]
        firmware_revision = device_info_root.xpath('./firmware_revision/text()')[0]
        description = device_info_root.xpath('./description/text()')[0]
        system_status = device_info_root.xpath('./system_status/text()')[0]
        protocol_services_supported = device_info_root.xpath(
            './protocol_services_supported/text()')[0]

        # self.local_device_address = dom.xpath('./@*[name()="host" or name()="port"]')

        self.thisDevice = LocalDeviceObject(
            objectName=name_key,
            objectIdentifier=int(id_key),
            location = location,
            vendorName=vendor_name_key,
            vendorIdentifier=int(vendor_identifier_key),
            maxApduLengthAccepted=int(apdu_length_key),
            segmentationSupported=segmentation_key,
            applicationSoftwareVersion = application_software_version,
            modelName = model_name,
            firmwareRevision = firmware_revision,
            description = description,
            systemStatus = system_status,
            protocolServicesSupported = int(protocol_services_supported)
        )

        self.bacnet_app = None

        logger.info('Conpot Bacnet initialized using the %s template.', template)

    def handle(self, data, address):
        session = conpot_core.get_session('bacnet', address[0], address[1])
        logger.info('New Bacnet connection from %s:%d. (%s)', address[0], address[1], session.id)
        session.add_event({'type': 'NEW_CONNECTION'})
        # I'm not sure if gevent DatagramServer handles issues where the
        # received data is over the MTU -> fragmentation
        if data:
            pdu = PDU()
            pdu.pduData = data
            # check for a BVLL header
            if (pdu.pduData[0] == '\x81'):
                logger.info('BVLL header found.')
                xpdu = BVLPDU()
                xpdu.decode(pdu)
                logger.info('Xpdu: %r.', xpdu)
                pdu = xpdu

                # make a more focused interpretation
                atype = bvl_pdu_types.get(pdu.bvlciFunction)
                if not atype:
                    logger.info('Unknown BVLL type: %r', pdu.bvlciFunction)
                    return pdu

                #decode it as one of the basic types
                try:
                    xpdu = pdu
                    bpdu = atype()
                    bpdu.decode(pdu)
                    logger.info('Bpdu: %r', bpdu)

                    pdu = bpdu

                    # lift the address for forwarded NPDU's
                    if atype is ForwardedNPDU:
                        pdu.pduSource = bpdu.bvlciAddress
                    # no deeper decoding for some
                    elif atype not in (DistributeBroadcastToNetwork, OriginalUnicastNPDU, OriginalBroadcastNPDU):
                        return pdu

                except Exception, err:
                    logger.error("DecodingError: %s", err)
                    return xpdu

            # check for version number
            if (pdu.pduData[0] != '\x01'):
                return None


            #it's an NPDU
            try:
                npdu = NPDU()
                npdu.decode(pdu)
                logger.info('Npdu: %s', npdu)
            except Exception, err:
                logger.error("DecodingError: %s", err)
                return None

            # application or network layer message
            if npdu.npduNetMessage is None:
                logger.info('Not a network layer message, try as an APDU')
                # decode as a generic APDU
                try:
                    xpdu = APDU()
                    xpdu.decode(npdu)
                    apdu = xpdu
                except Exception, err:
                    logger.error("DecodingError: %s", err)
                    return npdu

                # "lift" the source and destination address
                if npdu.npduSADR:
                    apdu.pduSource = npdu.npduSADR
                else:
                    apdu.pduSource = npdu.pduSource
                if npdu.npduDADR:
                    apdu.pduDestination = npdu.npduDADR
                else:
                    apdu.pduDestination = npdu.pduDestination

                # make a more focused interpretation
                atype = apdu_types.get(apdu.apduType)
                if not atype:
                    logger.info('Unknown APDU type: %s', apdu.apduType)
                    return apdu

                # decode it as one of the basic types
                try:
                    xpdu = apdu
                    apdu = atype()
                    apdu.decode(xpdu)
                    logger.info('Apdu: %s', apdu)
                except Exception, err:
                    logger.error("DecodingError: %s", err)
                    return xpdu

                self.bacnet_app.indication(apdu, address, self.thisDevice)
                self.bacnet_app.response(self.bacnet_app._response, address)

            else:
                # make a more focused interpretation
                ntype = npdu_types.get(npdu.npduNetMessage)
                if not ntype:
                    logger.info('no network layer decoder: %s', npdu.npduNetMessage)
                    return npdu
                logger.info('Ntype: %s', ntype)

                # deeper decoding
                try:
                    xpdu = npdu
                    npdu = ntype()
                    npdu.decode(xpdu)
                    logger.info('Npdu: %s', npdu)
                except Exception, err:
                    logger.error("DecodingError: %s", err)
                    return xpdu
                # self.bacnet_app.indication(apdu, address, self.thisDevice)
                # self.bacnet_app.response(self.bacnet_app._response, address)

        logger.info('Bacnet client disconnected %s:%d. (%s)', address[0], address[1], session.id)

    def start(self, host, port):
        connection = (host, port)
        self.server = DatagramServer(connection, self.handle)
        # start to init the socket
        self.server.start()
        self.server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # create application instance
        # not too beautifull, but the BACnetApp needs access to the socket's sendto method
        # this could properly be refactored in a way such that sending operates on it's own
        # (non-bound) socket.
        self.bacnet_app = BACnetApp(self.thisDevice, self.server)
        # get object_list and properties
        self.bacnet_app.get_objects_and_properties(self.dom)


        logger.info('Bacnet server started on: %s', connection)
        self.server.serve_forever()

    def stop(self):
        self.server.stop()
