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
import re
import sys
from bacpypes.pdu import GlobalBroadcast
import pdb

logger = logging.getLogger(__name__)

import bacpypes.object
from bacpypes.app import BIPSimpleApplication
from bacpypes.service.device import LocalDeviceObject

from bacpypes.constructeddata import Any
from bacpypes.apdu import APDU, apdu_types, confirmed_request_types, unconfirmed_request_types, Error,\
    ErrorPDU, RejectPDU, IAmRequest, IHaveRequest, ReadPropertyACK, ConfirmedServiceChoice, UnconfirmedServiceChoice, \
    complex_ack_types, error_types, ConfirmedRequestPDU, UnconfirmedRequestPDU, SimpleAckPDU, ComplexAckPDU, \
    SegmentAckPDU, AbortPDU
from bacpypes.pdu import PDU
from bacpypes.bvll import BVLPDU, BVLCI, ForwardedNPDU, \
    DistributeBroadcastToNetwork, OriginalUnicastNPDU, OriginalBroadcastNPDU
from bacpypes.npdu import NPDU, Address, npdu_types
from bacpypes.constructeddata import *
from bacpypes.primitivedata import *
from bacpypes.object import *
import ast

func = lambda s: s[:1].lower() + s[1:] if s else ''

class BACnetApp(BIPSimpleApplication):
    def __init__(self, device, datagram_server):
        self._request = None
        self._response = None
        self._response_service = None
        self.localDevice = device
        self.objectName = {device.objectName: device}
        self.objectIdentifier = {device.objectIdentifier: device}
        self.description = {device.description: device}
        self.location = {device.location: device}
        self.vendorName = {device.vendorName: device}
        self.vendorIdentifier = {device.vendorIdentifier: device},
        self.maxApduLengthAccepted = {device.maxApduLengthAccepted: device},
        self.segmentationSupported = {device.segmentationSupported: device},
        self.applicationSoftwareVersion = {device.applicationSoftwareVersion: device},
        self.modelName = {device.modelName: device},
        self.firmwareRevision = {device.firmwareRevision: device},
        self.description = {device.description: device},
        self.systemStatus = {device.systemStatus: device},
        self.protocolServicesSupported = {device.protocolServicesSupported: device},
        self.datagram_server = datagram_server

    def get_objects_and_properties(self, dom):
        # parse the bacnet template for objects and their properties
        device_property_list = dom.xpath('//bacnet/device_info/*')
        for prop in device_property_list:
            prop_key = prop.tag.lower().title()
            prop_key = re.sub("['_','-']", "", prop_key)
            prop_key = prop_key[0].lower() + prop_key[1:]
            if prop_key not in self.localDevice.propertyList.value and \
                            prop_key not in ['deviceIdentifier','deviceName']:
                self.add_property(prop_key, prop.text)

        object_list = dom.xpath('//bacnet/object_list/object/@name')
        for obj in object_list:
            # logger.info("construct objectlist: obj is %s", obj)
            property_list = dom.xpath('//bacnet/object_list/object[@name="%s"]/properties/*' % obj)
            for prop in property_list:
                if prop.tag == 'object_type':
                    object_type = re.sub('-', ' ', prop.text)#.lower().title()
                    object_type = re.sub(' ', '', object_type) + 'Object'
                    # logger.info('object_type is %s', object_type)
            try:
                device_object = getattr(bacpypes.object, object_type)()
            except NameError:
                logger.critical('Non-existent BACnet object type')
                sys.exit(3)
            #setup objectName
            setattr(device_object,'objectName', obj)
            for prop in property_list:
                prop_key = prop.tag.lower().title()
                prop_key = re.sub("['_','-']", "", prop_key)
                prop_key = prop_key[0].lower() + prop_key[1:]

                if prop_key == 'objectType':
                    prop_val = prop.text.lower().title()
                    prop_val = re.sub(" ", "", prop_val)
                    prop_val = prop_val[0].lower() + prop_val[1:]
                prop_val = prop.text
                try:
                    if prop_key == 'objectIdentifier':
                        # logger.info('OI, prop_key is %s', prop_key)
                        # logger.info('OI, prop_val is %s', prop_val)
                        device_object.objectIdentifier = int(prop_val)
                    else:
                        # logger.info('Else, prop_key is %s', prop_key)
                        # logger.info('Else, prop_val is %s', prop_val)
                        setattr(device_object, prop_key, prop_val)
                        device_object.propertyList.append(prop_key)
                except bacpypes.object.PropertyError:
                    logger.critical('Non-existent BACnet property type')
                    sys.exit(3)
            self.add_object(device_object)
        # logger.info('objectList: %r', self.localDevice.objectList)
        # logger.info('objectName: %r', self.objectName)

    def add_object(self, obj):
        object_name = obj.objectName
        # logger.info('addobj: %s', object_name)
        if not object_name:
            raise RuntimeError("object name required")
        object_identifier = obj.objectIdentifier
        if not object_identifier:
            raise RuntimeError("object identifier required")
        if object_name in self.objectName:
            raise RuntimeError("object already added with the same name")
        if object_identifier in self.objectIdentifier:
            raise RuntimeError("object already added with the same identifier")

        self.objectName[object_name] = obj
        self.objectIdentifier[object_identifier] = obj
        self.localDevice.objectList.append(object_identifier)

    def add_property(self, prop_name, prop_value):
        if not prop_name:
            raise RuntimeError("property name required")
        if not prop_value:
            raise RuntimeError("property value required")

        setattr(self.localDevice, prop_name, prop_value)
        self.localDevice.propertyList.append(prop_name)

    def iAm(self, *args):
        self._response = None
        return

    def iHave(self, *args):
        self._response = None
        return

    def whoIs(self, request, address, invoke_key, device):
        # Limits are optional (but if used, must be paired)
        execute = False
        try:
            if (request.deviceInstanceRangeLowLimit is not None) and \
                    (request.deviceInstanceRangeHighLimit is not None):
                logger.info('device ID is %s', self.objectIdentifier.keys()[0][1])
                if (request.deviceInstanceRangeLowLimit == 4194303) or (request.deviceInstanceRangeHighLimit == 4194303):
                    execute = True
                elif (request.deviceInstanceRangeLowLimit > self.objectIdentifier.keys()[0][1]
                        > request.deviceInstanceRangeHighLimit):
                    logger.info('Bacnet WhoIsRequest out of range')
                elif ((self.objectIdentifier.keys()[0][1] <= request.deviceInstanceRangeHighLimit) and \
                        (request.deviceInstanceRangeLowLimit <= self.objectIdentifier.keys()[0][1])):
                    execute = True
                else:
                    logger.info('else.')
                    execute = True
            else:
                execute = True
        except AttributeError:
            execute = True

        if execute:
            self._response_service = 'IAmRequest'
            self._response = IAmRequest()
            self._response.pduDestination = GlobalBroadcast()
            self._response.iAmDeviceIdentifier = device.objectIdentifier
            self._response.maxAPDULengthAccepted = int(getattr(self.localDevice, 'maxApduLengthAccepted'))
            self._response.segmentationSupported = getattr(self.localDevice, 'segmentationSupported')
            self._response.vendorID = int(getattr(self.localDevice, 'vendorIdentifier'))

    def whoHas(self, request, address, invoke_key, device):
        execute = False
        try:
            if (request.deviceInstanceRangeLowLimit is not None) and \
                    (request.deviceInstanceRangeHighLimit is not None):
                if (request.deviceInstanceRangeLowLimit > self.objectIdentifier.keys()[0][1]
                        > request.deviceInstanceRangeHighLimit):
                    logger.info('Bacnet WhoHasRequest out of range')
                else:
                    execute = True
            else:
                execute = True
        except AttributeError:
            execute = True

        if execute:
            for obj in device.objectList.value[2:]:
                if int(request.object.objectIdentifier[1]) == obj[1] and \
                                request.object.objectIdentifier[0] == obj[0]:
                    objName = self.objectIdentifier[obj].objectName
                    self._response_service = 'IHaveRequest'
                    self._response = IHaveRequest()
                    self._response.pduDestination = GlobalBroadcast()
                    self._response.deviceIdentifier = self.objectIdentifier.keys()[0][1]
                    self._response.objectIdentifier = obj[1]
                    self._response.objectName = objName
                    break
            else:
                logger.info('Bacnet WhoHasRequest: no object found')

    def readProperty(self, request, address, invoke_key, device):
        # Read Property
        # TODO: add support for PropertyArrayIndex handling;
        logger.info('RP request: %s, address: %s, invoke_key: %s, device: %s', request, address, invoke_key, device)
        logger.info('Request obj id: %s, prop id: %s', request.objectIdentifier, request.propertyIdentifier)

        #ReadProperty on device information
        if request.objectIdentifier[0] == 'device':
            # obj = self.localDevice
            propName = request.propertyIdentifier
            propValue = getattr(device, propName)
            logger.info('ReadProperty: device property %s: %s, ', propName, propValue)
            if propValue:
                logger.info('Prepare response')
                # propValue = propValue.lower().title()
                # propValue = re.sub("['_','-']", "", propValue)
                # propValue = re.sub(" ", "", propValue)
                # propValue = propValue[0].lower() + propValue[1:]
                # propType = propValue.datatype()
                # logger.info('%r', propType)
                self._response_service = 'ReadPropertyACK'
                self._response = ReadPropertyACK(context = request)
                self._response.pduDestination = address
                self._response.apduInvokeID = invoke_key
                self._response.objectIdentifier = device.objectIdentifier[1]
                self._response.objectName = 'device'
                self._response.propertyIdentifier = propName
                # datatype = type(propType)
                # if issubclass(datatype, Real):
                #     logger.info('Real Type.')
                propValue = str(propValue)
                if (propName == 'objectIdentifier' or propName == 'vendorIdentifier' or
                            propName == 'maxApduLengthAccepted' or propName == 'protocolServicesSupported'):
                    propValue = Integer(ast.literal_eval(propValue))
                else:
                    propValue = CharacterString(propValue)
                # self._response.propertyValue = propValue
                self._response.propertyValue = Any()
                self._response.propertyValue.cast_in(propValue)
                return
                # try:
                #     datatype = type(propType)
                #     if issubclass(datatype, Real):
                #         logger.info('Real Type.')
                #         propValue = str(propValue.strip())
                #         propValue = ast.literal_eval(propValue)
                #     logger.info('dataType is %r', datatype)
                #     if issubclass(datatype, Atomic):
                #         value = datatype(propValue)
                #     elif issubclass(datatype, Array) and (request.propertyArrayIndex is not None):
                #         if request.propertyArrayIndex == 0:
                #             value = Unsigned(propValue)
                #         elif issubclass(datatype.subtype, Atomic):
                #             value = datatype.subtype(propValue)
                #         elif not isinstance(propValue, datatype.subtype):
                #             logger.error( "invalid result datatype, expecting %s and got %s" \
                #         % (datatype.subtype.__name__, type(propValue).__name__))
                #     elif not isinstance(propValue, datatype):
                #         logger.error( "invalid result datatype, expecting %s and got %s" \
                #     % (datatype.__name__, type(propValue).__name__))
                #
                #     self._response.propertyValue = Any()
                #     self._response.propertyValue.cast_in(value)
                #     return
                # except Exception, err:
                #     logger.info('Bacnet ReadProperty: Object has no property %s', request.propertyIdentifier)
                #     self._response = Error(errorClass='object', errorCode='unknownProperty', context=request)
                #     self._response_service = 'Error'
                #     self._response.pduDestination = address
                #     self._response.apduInvokeID = invoke_key
                #     self._response.apduService = 0x0c
            else:
                #no such property in device object
                logger.info('Bacnet ReadProperty: Device Object has no property %s', request.propertyIdentifier)
                self._response = Error(errorClass='object', errorCode='unknownProperty', context=request)
                self._response_service = 'Error'
                self._response.pduDestination = address
                self._response.apduInvokeID = invoke_key
                self._response.apduService = 0x0c
                return
        for obj in device.objectList.value[2:]:
            if int(request.objectIdentifier[1]) == obj[1] and \
                            request.objectIdentifier[0] == obj[0]:
                logger.info('Matched object ID: %s', obj)
                objName = self.objectIdentifier[obj].objectName
                logger.info('Matched object name %s', objName)
                for prop in self.objectIdentifier[obj].properties:
                    if request.propertyIdentifier == prop.identifier:
                        logger.info('Request propertyID %s', request.propertyIdentifier)
                        propName = prop.identifier
                        propValue = prop.ReadProperty(
                            self.objectIdentifier[obj])
                        propValue = propValue.lower().title()
                        propValue = re.sub("['_','-']", "", propValue)
                        propValue = re.sub(" ", "", propValue)
                        propValue = propValue[0].lower() + propValue[1:]
                        propType = prop.datatype()
                        logger.info('propName is %s, propValue is %s, propType is %s', propName, propValue, propType)
                        self._response_service = 'ReadPropertyACK'
                        self._response = ReadPropertyACK(context = request)
                        self._response.pduDestination = address
                        self._response.apduInvokeID = invoke_key
                        self._response.objectIdentifier = obj[1]
                        self._response.objectName = objName
                        self._response.propertyIdentifier = propName
                        # self._response.propertyArrayIndex = 1#True

                        # for p in dir(sys.modules[propType.__module__]):
                        #     _obj = getattr(sys.modules[propType.__module__], p)
                        #     try:
                        #         if type(propType) == _obj:
                        #             logger.info('_obj %r, propType is %r', _obj, propType)
                        #             break
                        #     except TypeError:
                        #         pass
                        # value = ast.literal_eval(propValue)
                        #
                        # self._response.propertyValue = Any(_obj(value))

                        #try to encode property
                        try:
                            datatype = type(propType)
                            if issubclass(datatype, Real):
                                logger.info('Real Type.')
                                propValue = str(propValue.strip())
                                propValue = ast.literal_eval(propValue)
                            logger.info('dataType is %r', datatype)
                            if issubclass(datatype, Atomic):
                                value = datatype(propValue)
                            elif issubclass(datatype, Array) and (request.propertyArrayIndex is not None):
                                if request.propertyArrayIndex == 0:
                                    value = Unsigned(propValue)
                                elif issubclass(datatype.subtype, Atomic):
                                    value = datatype.subtype(propValue)
                                elif not isinstance(propValue, datatype.subtype):
                                    logger.error( "invalid result datatype, expecting %s and got %s" \
                                % (datatype.subtype.__name__, type(propValue).__name__))
                            elif not isinstance(propValue, datatype):
                                logger.error( "invalid result datatype, expecting %s and got %s" \
                            % (datatype.__name__, type(propValue).__name__))

                            self._response.propertyValue = Any()
                            self._response.propertyValue.cast_in(value)
                        except Exception, err:
                            logger.info('Bacnet ReadProperty: Object has no property %s', request.propertyIdentifier)
                            self._response = Error(errorClass='object', errorCode='unknownProperty', context=request)
                            self._response_service = 'Error'
                            self._response.pduDestination = address
                            self._response.apduInvokeID = invoke_key
                            self._response.apduService = 0x0c
                        return


                logger.info('Bacnet ReadProperty: Object has no property %s', request.propertyIdentifier)
                self._response = Error(errorClass='object', errorCode='unknownProperty', context=request)
                self._response_service = 'Error'
                self._response.pduDestination = address
                self._response.apduInvokeID = invoke_key
                self._response.apduService = 0x0c
                return
                # self._response.errorClass
                # self._response.errorCode

        logger.info('BACnet ReadProperty: No such object %s', request.objectIdentifier)
        self._response = Error(errorClass='object', errorCode='unknownObject', context=request)#ErrorPDU(0x0c, invoke_key)
        self._response_service = 'Error'
        self._response.pduDestination = address
        self._response.apduInvokeID = invoke_key
        self._response.apduService = 0x0c
        return

    def writeProperty(self, request, address, invoke_key, device):
        # Write Property
        logger.info('WP request: %s, address: %s, invoke_key: %s, device: %s', request, address, invoke_key, device)
        logger.info('Request obj id: %s, prop id: %s', request.objectIdentifier, request.propertyIdentifier)
        obj = request.objectIdentifier
        prop = request.propertyIdentifier
        # any = Any()
        propVal = request.propertyValue
        priority = request.priority
        logger.info('Priority is %s', priority)

        # get the datatype, special case for null
        if request.propertyValue.is_application_class_null():
            datatype = Null
        # else:
            # datatype = request.propertyValue.datatype()#obj.get_datatype(apdu.propertyIdentifier)
        # logger.info('datatype is %s', datatype)

        # special case for array parts, others are managed by cast_out
        # if issubclass(datatype, Array) and (request.propertyArrayIndex is not None):
        #     if request.propertyArrayIndex == 0:
        #         value = request.propertyValue.cast_out(Unsigned)
        #     else:
        #         value = request.propertyValue.cast_out(datatype.subtype)
        # else:
        #     value = request.propertyValue.cast_out(datatype)
        #
        # logger.info('value is %s', value)
        # propArrIdx = request.propertyArraryIndex

        # datatype = obj.get_datatype(request.objectIdentifier)
        # logger.info('val is %s',request.propertyValue.cast_out(Unsigned))
        # request.propertyArraryIndex

        # propVal = request.propertyValue
        # propArrIdx = request.propertyArraryIndex
        # priority = request.priority
        logger.info('WP. obj is %r, prop is %r, propVal is %r,  priority is %r', obj, prop, propVal,  priority)
        if obj not in device.objectList.value[2:]:
            logger.info('WriteProperty: obj does not exist.')
            #obj does not exist
            logger.info('BACnet ReadProperty: No such object %s', request.objectIdentifier)
            self._response = Error(errorClass='object', errorCode='unknownObject', context=request)
            self._response_service = 'Error'
            self._response.pduDestination = address
            self._response.apduInvokeID = invoke_key
            self._response.apduService = 0x0f
        else:
            #obj is already there
            logger.info('WriteProperty: obj exists.')
            #check if property exist
            for element in self.objectIdentifier[obj].properties:
                logger.info('WP: properties:%r', element.identifier)
                if element.identifier == prop:
                    #property exists
                    logger.info("WriteProperty: property exists.")
                    propName = element.identifier
                    # propVal = ast.literal_eval(propVal)
                    propVal = propVal.cast_out(Real)
                    element.WriteProperty(self.objectIdentifier[obj], propVal)
                    propType = element.datatype()
                    logger.info('propName is %s, propValue is %s, propType is %s', propName, propVal, propType)
                    self._response_service = 'SimpleAck'
                    self._response = SimpleAckPDU(context = request)
                    self._response.pduDestination = address
                    self._response.apduInvokeID = invoke_key
                    return
                    # self._response.objectIdentifier = obj[1]
                    # self._response.objectName = objName
                    # self._response.propertyIdentifier = propName
            # property not exist
            logger.info('BACnet WriteProperty: No such property %s', request.propertyIdentifier)
            self._response_service = 'Error'
            self._response = Error(errorClass='object', errorCode='unknownProperty', context=request)
            self._response.pduDestination = address
            self._response.apduInvokeID = invoke_key
            self._response.apduService = 0x0f
            return


    def indication(self, apdu, address, device):
        # logging the received PDU type and Service request
        logger.info('Entering indication function.')
        request = None
        apdu_type = apdu_types.get(apdu.apduType)
        invoke_key = apdu.apduInvokeID
        logger.info('Bacnet PDU received from %s:%d. (%s)', address[0], address[1], apdu_type.__name__)
        if apdu_type.pduType == 0x0:
            # Confirmed request handling
            apdu_service = confirmed_request_types.get(apdu.apduService)
            logger.info('Bacnet indication from %s:%d. (%s)', address[0], address[1], apdu_service.__name__)
            try:
                request = apdu_service()
                request.decode(apdu)
            except (AttributeError, RuntimeError) as e:
                logger.warning('Bacnet indication: Invalid service. Error: %s' % e)
                return
            except bacpypes.errors.DecodingError:
                pass

            for key, value in ConfirmedServiceChoice.enumerations.items():
                if apdu_service.serviceChoice == value:
                    logger.info("apdu_service choice is %d", apdu_service.serviceChoice)
                    try:
                        getattr(self, key)(
                            request, address, invoke_key, device)
                        break
                    except AttributeError:
                        logger.error('Indication: Not implemented Bacnet command')
                        self._response_service = 'Error'
                        self._response = Error(errorClass='object', errorCode='unknownProperty', context=request)
                        self._response.pduDestination = address
                        self._response.apduInvokeID = invoke_key
                        self._response.apduService = apdu_service.serviceChoice
                        return
            else:
                logger.info('Bacnet indication: Invalid confirmed service choice (%s)', apdu_service.__name__)
                self._response = None
                return

        # Unconfirmed request handling
        elif apdu_type.pduType == 0x1:
            apdu_service = unconfirmed_request_types.get(apdu.apduService)
            logger.info('Bacnet indication from %s:%d. (%s)', address[0], address[1], apdu_service.__name__)
            try:
                request = apdu_service()
                request.decode(apdu)
            except (AttributeError, RuntimeError) as e:
                logger.warning('Bacnet indication: Invalid service. Error: %s' % e)
                self._response = None
                return
            except bacpypes.errors.DecodingError:
                pass

            for key, value in UnconfirmedServiceChoice.enumerations.items():
                if apdu_service.serviceChoice == value:
                    try:
                        getattr(self, key)(
                            request, address, invoke_key, device)
                        break
                    except AttributeError:
                        logger.error('Not implemented Bacnet command')
                        self._response_service = 'Error'
                        self._response = Error(errorClass='object', errorCode='unknownProperty', context=request)
                        self._response.pduDestination = address
                        self._response.apduInvokeID = invoke_key
                        self._response.apduService = apdu_service.serviceChoice
                        return
            else:
                # Unrecognized services
                logger.info(
                    'Bacnet indication: Invalid unconfirmed service choice (%s)', apdu_service)
                self._response_service = 'Error'
                self._response = Error(errorClass='services', errorCode='serviceRequestDenied', context=request)
                self._response.pduDestination = address
                self._response.apduInvokeID = invoke_key
                self._response.apduService = apdu_service.serviceChoice
                return
        # ignore the following
        elif apdu_type.pduType == 0x2:
            # simple ack pdu
            self._response = None
            return
        elif apdu_type.pduType == 0x3:
            # complex ack pdu
            self._response = None
            return
        elif apdu_type.pduType == 0x4:
            # segment ack
            self._response = None
            return
        elif apdu_type.pduType == 0x5:
            # error pdu
            self._response = None
            return
        elif apdu_type.pduType == 0x6:
            # reject pdu
            self._response = None
            return
        elif apdu_type.pduType == 0x7:
            # abort pdu
            self._response = None
            return
        elif 0x8 <= apdu_type.pduType <= 0xf:
            # reserved
            self._response = None
            return
        else:
            # non-BACnet PDU types
            logger.info('Bacnet Unrecognized service')
            self._response = None
            return

    # socket not actually socket, but DatagramServer with sendto method
    def response(self, response_apdu, address):
        # logger.info('Entering response function.')
        # logger.info('response_apdu is %r', response_apdu)
        if response_apdu is None:
            return

        if (isinstance(response_apdu, RejectPDU) or isinstance(response_apdu,ErrorPDU)):
            logger.info('Response: RejectPDU or ErrorPDU: %r.', response_apdu)
            apdu = APDU()
            response_apdu.encode(apdu)
            npdu = NPDU()
            apdu.encode(npdu)
            obnpdu = OriginalUnicastNPDU()
            npdu.encode(obnpdu)
            bvlp = BVLPDU()
            obnpdu.encode(bvlp)
            pdu = PDU()
            bvlp.encode(pdu)
            self.datagram_server.sendto(pdu.pduData, address)
            return

        try:
            apdu = APDU()
            response_apdu.encode(apdu)
        except Exception, err:
            logger.error('EncodeError: apdu: %s', err)
            return apdu

        apdu_type = apdu_types.get(apdu.apduType)
        # logger.info("apdu_type is %s, apdu.apduType is %s, pduType is %s", apdu_type, apdu.apduType, apdu_type.pduType)
        # logger.info("apduInvokeID is %s",apdu.apduInvokeID)
        # logger.info('apdu is %r', apdu.pduData)
        # logger.info(":".join("{:02x}".format(ord(c)) for c in apdu.pduData))
        # "lift" source and destination address

        npdu = NPDU()
        try:
            apdu.encode(npdu)
        except Exception, err:
            logger.error('EncodeError: npdu: %s', err)
        npdu.npduHopCount = int(255)
        # logger.info('npdu.pduData is %r', npdu.pduData)
        # logger.info(":".join("{:02x}".format(ord(c)) for c in npdu.pduData))


        obnpdu = OriginalUnicastNPDU()
        if (apdu.apduType == ConfirmedRequestPDU.pduType or apdu.apduType == ComplexAckPDU.pduType or apdu.apduType == SimpleAckPDU.pduType) :
            logger.info('Isinstacne Unicast.')
            obnpdu = OriginalUnicastNPDU()
        elif (apdu.apduType == UnconfirmedRequestPDU.pduType):
            logger.info('Isinstacne Broadcast.')
            obnpdu = OriginalBroadcastNPDU()
        elif (apdu.apduType == DistributeBroadcastToNetwork.messageType):
            logger.info('Isinstacne DistributeBroadcastToNetwork.')
            obnpdu = DistributeBroadcastToNetwork()
        elif (apdu.apduType == ForwardedNPDU.messageType):
            logger.info('Isinstacne ForwardedNPDU.')
            npdu.pduSource = apdu.bvlciAddress
        else:
            logger.info('Error: blvi function not implemented.')

        try:
            npdu.encode(obnpdu)
        except Exception, err:
            logger.error('Obnpdu encode error: %s', err)

        # logger.info('Obnpdu.pduData is %r', obnpdu.pduData)
        # logger.info(":".join("{:02x}".format(ord(c)) for c in obnpdu.pduData))

        bvlp = BVLPDU()
        try:
            obnpdu.encode(bvlp)
        except Exception, err:
            logger.error('Bvlp encode error: %s', err)

        # logger.info('bvlp.pduData is %r', bvlp.pduData)

        pdu = PDU()

        try:
            bvlp.encode(pdu)
        except Exception, err:
            logger.error("Pdu encode error: %s", err)

        # if isinstance(response_apdu, RejectPDU) or isinstance(response_apdu, ErrorPDU):
        #     self.datagram_server.sendto(pdu.pduData, address)
        # else:
        if pdu.pduDestination == '*:*':
            # broadcast
            # sendto operates under lock
            self.datagram_server.sendto(pdu.pduData, ('255.255.255.255', address[1]))
        else:
            # sendto operates under lock
            self.datagram_server.sendto(pdu.pduData, address)
            # logger.info('pdu.pduData: %r',":".join("{:02x}".format(ord(c)) for c in pdu.pduData))
        logger.info('Bacnet response sent to %s (%s:%s)',
                response_apdu.pduDestination, apdu_type.__name__, self._response_service)
