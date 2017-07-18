import xml.etree.cElementTree as ET
import lxml.etree as etree
import csv



device_id = ''

with open('read10.195.2.215.csv') as csvfile:
    spamreader = csv.reader(csvfile, delimiter = ',')
    count1 = 0
    count2 = 0
    #analog object properties
    analog_otype = []
    analog_oid = []
    analog_oname = []
    analog_pval = []
    analog_unit = []

    #binary object properties
    binary_otype=[]
    binary_oid=[]
    binary_active_txt=[]
    binary_inactive_txt=[]
    binary_oname=[]
    binary_pval=[]

    #trendlog object properties
    trend_oid = []
    trend_oname = []
    #schedule object properties
    schedule_oid = []
    schedule_oname = []
    #notification object properties
    notification_oid = []
    notification_oname = []

    for row in spamreader:
        #setup device id
        if (row[0].split(' ')[0] == 'Device'):
            device_id = row[0].split(' ')[1]
            print device_id
        if (row[0].split(' ')[0] == 'Analog'):
            count1 = count1 + 1
            #print (", ".join(row))
            if (count1 % 3 == 0):
                analog_otype.append(row[0].split(' ')[0]+row[0].split(' ')[1])
                analog_oid.append(row[0].split(' ')[2])
            if (row[1] == 'Object name'):
                analog_oname.append(row[2])
            if (row[1] == 'Present value'):
                analog_pval.append(row[2])
            if (row[1] == 'Units'):
                analog_unit.append(row[2])
        elif (row[0].split(' ')[0] == "Binary"):
            count2 = count2 + 1
            if (count2 % 4 == 0):
                binary_otype.append(row[0].split(' ')[0]+row[0].split(' ')[1])
                binary_oid.append(row[0].split(' ')[2])
            if (row[1] == 'Active text'):
                binary_active_txt.append(row[2])
            if (row[1] == 'Inactive text'):
                binary_inactive_txt.append(row[2])
            if (row[1] == 'Object name'):
                binary_oname.append(row[2])
            if (row[1] =='Present value'):
                binary_pval.append(row[2])
        elif (row[0].split(' ')[0] == "Trend"):
            trend_oid.append(row[0].split(' ')[2])
            trend_oname.append(row[2])
        elif (row[0].split(' ')[0] == "Schedule"):
            schedule_oid.append(row[0].split(' ')[1])
            schedule_oname.append(row[2])
        elif (row[0].split(' ')[0] == "Notification"):
            notification_oid.append(row[0].split(' ')[2])
            notification_oname.append(row[2])

    #print analog_oid, analog_oname, analog_pval, analog_unit
    #print binary_otype, binary_oid, binary_active_txt, binary_inactive_txt, binary_oname, binary_pval


root = ET.Element("bacnet")
root.set("enabled", "True")
root.set("host", "0.0.0.0")
root.set("port", "47808")

device = ET.SubElement(root, "device_info")

device_name = ET.SubElement(device, "device_name")
device_name.text = "SystemName"
device_identifier = ET.SubElement(device, "device_identifier")
device_identifier.text = device_id
location = ET.SubElement(device, "location")
location.text = "Main Bldg Boiler Rm"
vendor_name = ET.SubElement(device, "vendor_name")
vendor_name.text = "Siemens Industry Inc., Bldg Tech"
vendor_identifier = ET.SubElement(device, "vendor_identifier")
vendor_identifier.text = "313"
max_apdu_length_accepted = ET.SubElement(device, "max_apdu_length_accepted")
max_apdu_length_accepted.text = "1024"
segmentation_supported = ET.SubElement(device, "segmentation_supported")
segmentation_supported.text = "segmentedBoth"
application_software = ET.SubElement(device, "application_software_version")
application_software.text = "BME1265_0040"
model_name = ET.SubElement(device, "model_name")
model_name.text = "Siemens BACnet Field Panel"
firmware = ET.SubElement(device, "firmware_revision")
firmware.text = "PXME V3.4 BACnet 4.3g"
description = ET.SubElement(device, "description")
description.text = "HRBB FP01"
description = ET.SubElement(device, "system_status")
description.text = "operational"
description = ET.SubElement(device, "protocol_services_supported")
description.text = "25971167232"

object_list = ET.SubElement(root, "object_list")

# construct analog objects into xtree
for i in range(len(analog_unit)):
    object = ET.SubElement(object_list, "object")
    object.set("name", analog_oname[i])
    properties = ET.SubElement(object, "properties")
    object_identifier = ET.SubElement(properties, "object_identifier")
    object_identifier.text = analog_oid[i]
    object_type = ET.SubElement(properties, "object_type")
    object_type.text = analog_otype[i]
    present_value = ET.SubElement(properties, "present_value")
    present_value.text = analog_pval[i]
    units = ET.SubElement(properties, "units")
    units.text = analog_unit[i]

# construct binary objects into xtree
for i in range(len(binary_pval)):
    object = ET.SubElement(object_list, "object")
    object.set("name", binary_oname[i])
    properties = ET.SubElement(object, "properties")
    object_identifier = ET.SubElement(properties, "object_identifier")
    object_identifier.text = binary_oid[i]
    object_type = ET.SubElement(properties, "object_type")
    object_type.text = binary_otype[i]
    present_value = ET.SubElement(properties, "present_value")
    present_value.text = binary_pval[i]
    active_txt = ET.SubElement(properties, "active_text")
    active_txt.text = binary_active_txt[i]
    inactive_txt = ET.SubElement(properties, "inactive_text")
    inactive_txt.text = binary_inactive_txt[i]

# construct trend log objects into xtree
for i in range(len(trend_oname)):
    object = ET.SubElement(object_list, "object")
    object.set("name", trend_oname[i])
    properties = ET.SubElement(object, "properties")
    object_identifier = ET.SubElement(properties, "object_identifier")
    object_identifier.text = trend_oid[i]
    object_type = ET.SubElement(properties, "object_type")
    object_type.text = "TrendLog"

# construct notification objects into xtree
for i in range(len(notification_oname)):
    object = ET.SubElement(object_list, "object")
    object.set("name", notification_oname[i])
    properties = ET.SubElement(object, "properties")
    object_identifier = ET.SubElement(properties, "object_identifier")
    object_identifier.text = notification_oid[i]
    object_type = ET.SubElement(properties, "object_type")
    object_type.text = "NotificationClass"

# construct trend log objects into xtree
for i in range(len(schedule_oname)):
    object = ET.SubElement(object_list, "object")
    object.set("name", schedule_oname[i])
    properties = ET.SubElement(object, "properties")
    object_identifier = ET.SubElement(properties, "object_identifier")
    object_identifier.text = schedule_oid[i]
    object_type = ET.SubElement(properties, "object_type")
    object_type.text = "Schedule"

tree = ET.ElementTree(root)
tree.write("10.195.2.215.xml")
x = etree.parse("10.195.2.215.xml")
print etree.tostring(x, pretty_print = True)


