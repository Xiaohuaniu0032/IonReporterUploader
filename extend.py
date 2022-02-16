#!/usr/bin/python
# Copyright (C) 2012 Ion Torrent Systems, Inc. All Rights Reserved
# vim: tabstop=4 shiftwidth=4 softtabstop=4 noexpandtab
# Ion Plugin - Ion Reporter Uploader

import glob
import json
import os
import requests
import urllib
import subprocess
import base64
import re

pluginName = 'IonReporterUploader'
pluginDir = ""
debugMode = 0    # this needs a file /tmp/a.txt   existing and 777 permissions

def IRULibraryTestPrint(x):
    print "IRULibrary: ", x
    return

def testBucket(bucket):
    return bucket


# Writes to debug file
# import pdb; pdb.set_trace() -> helps to debug
def write_debug_log(text):     # this needs a file /tmp/a.txt   existing and 777 permissions, and dont forget to switch on the global variable debugMode
    if (debugMode==0):
        return
    log_file = "/tmp/a.txt"
    file = open(log_file, "a")
    file.write(text)
    file.write("\n")
    return log_file

def get_plugin_dir():
    return os.path.dirname(__file__)

def set_classpath():
    plugin_dir=get_plugin_dir()

    jarscmd="find " + plugin_dir + "/lib/java/shared" + "  |grep \"jar$\" |xargs |sed 's/ /:/g'"
    #write_debug_log("jarscmd="+ jarscmd)
    proc = subprocess.Popen(jarscmd, shell=True, stdout=subprocess.PIPE)
    (jarsout, jarserr)= proc.communicate()
    #exitCode = proc.returncode
    #write_debug_log("jarsout="+ jarsout)
    if (jarserr):
        write_debug_log("jarserr="+ jarserr)
    classpath_str = plugin_dir + "/lib/java/shared:" + jarsout
    #write_debug_log("classpath="+ classpath_str)
    os.environ["CLASSPATH"] = classpath_str
    #write_debug_log("classpath from os ="+ os.getenv('CLASSPATH'))
    if (os.getenv("LD_LIBRARY_PATH")):
        ld_str = plugin_dir + "/lib:" + os.getenv("LD_LIBRARY_PATH")
    else:
        ld_str = plugin_dir + "/lib"
        os.environ["LD_LIBRARY_PATH"] = ld_str
    return classpath_str

def get_httpResponseFromSystemTools(cmd):
    write_debug_log("systemtools  cmd = "+ cmd)
    proc = subprocess.Popen( cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()
    exitCode = proc.returncode
    write_debug_log("systemtools  out = "+ out)
    #print(">>systemtools  out = ", out)
    #print(">>systemtools  err = ", err)
    if (err):
       write_debug_log("systemtools  err = "+ err)
    else:
       err=""
    write_debug_log("systemtools  exitCode = "+ str(exitCode))
    if (exitCode != 0):
        return {"status": "false", "error": err, "exitCode":exitCode, "stdout": out}
    else:
        return {"status": "true", "error": err, "exitCode":exitCode, "stdout": out}
    #return {"status": "false", "error": err, "exitCode":exitCode, "stdout": out}

def get_httpResponseFromSystemToolsAsJson(cmd):
    result = get_httpResponseFromSystemTools(cmd)

    if (result["status"] != "true"):
        return result
    if ((result["error"] != "") and ("NTLM authentication" not in result["error"])):
        result["status"]="false"
        return result
    j = {}
    try:
        j=json.loads(result["stdout"])
        result["json"]=j
        return result
    except ValueError:
        result["status"]="false"
        result["error"]="error decoding output as json "+ result["stdout"]
        result["json"]=""
        return result

def get_httpResponseFromIRUJavaAsJson(cmd):
    plugin_dir=get_plugin_dir()

    #TBD find with cmd = find java/ |grep bin |grep "bin\/java$"
    javaBin=plugin_dir+ "/"+ "java/amazon-corretto-11.0.7.10.1-linux-x64/bin/java"
    #javaBin=plugin_dir+ "/"+ "java/jre/openjdk-7-jre-headless/usr/lib/jvm/java-7-openjdk-amd64/jre/bin/java"
    #javaBin="java"

    javaMemOptionsForJavaBelow_1_8=" -XX:MaxPermSize=256m"
    #javaMemOptions=javaMemOptionsForJavaBelow_1_8
    javaMemOptions=""       # perm size not required when using internally embedded java 1.8 and above.

    set_classpath()
    cpstring=os.getenv('CLASSPATH')
    cpstring=cpstring.strip('\n')

    result={}
    #write_debug_log(javaBin + " -Xms4g -Xmx4g"+ javaMemOptions + " -Djsse.enableSNIExtension=false -Dlog.home=/tmp com.lifetechnologies.ionreporter.clients.irutorrentplugin.Launcher " + cmd)
    result=get_httpResponseFromSystemToolsAsJson(javaBin + " -Xms4g -Xmx4g" + " -cp " + cpstring +" " + javaMemOptions + " -Djsse.enableSNIExtension=false -Dlog.home=/tmp com.lifetechnologies.ionreporter.clients.irutorrentplugin.Launcher " + cmd)
    return result


def configs(bucket):
    user = str(bucket["user"])
    if "request_get" in bucket:
        #grab the config blob
        config = bucket.get("config", {})
        all_userconfigs = config.get("userconfigs", {})
        userconfigs = all_userconfigs.get(user, [])

        active_configs = []

        for userconfig in userconfigs:
            #remove the _version_cache cruft
            if userconfig.get("_version_cache", False):
                del userconfig["_version_cache"]

            #only if the version is not 1 add it to the list to return
            if userconfig.get("version", False):
                if userconfig["version"][2] != "1":
                    active_configs.append(userconfig)

        return active_configs


def getSelectedIRAccountFromBucket(bucket):
    user = str(bucket["user"])
    if "request_get" in bucket:
        #get the id from the querystring
        config_id = bucket["request_get"].get("id", False)

        #grab the config blob
        config = bucket.get("config", {})
        all_userconfigs = config.get("userconfigs", {})
        userconfigs = all_userconfigs.get(user)

        if (userconfigs == None):
            return {"status": "false", "error": "Error getting list of IR accounts from plugin configuration"}

        #now search for the config with the id given
        for userconfig in userconfigs:
            if userconfig.get("id", False):
                if userconfig.get("id") == config_id:
                    selected = {}
                    selected["irAccount"] = userconfig
                    return {"status": "true", "error": "none","selectedAccount": selected}

        #if we got all the way down here it failed
        return {"status": "false", "error": "No such IR account"}
    return {"status": "false", "error": "request was not a GET "}




#example access http://10.43.24.24/rundb/api/v1/plugin/IonReporterUploader/extend/getProductionURLS/?format=json&id=mt6irqz9rtrc4i6y34fio9
def getProductionURLS(bucket):
        versions = {"urls": []}

        IR54 = {"IRVersion" : "IR54", "server" : "40.dataloader.ionreporter.thermofisher.com",
                "port" : "443", "protocol" : "https"
        }
        IR52 = {"IRVersion" : "IR52", "server" : "40.dataloader.ionreporter.thermofisher.com",
                "port" : "443", "protocol" : "https"
        }
        IR50 = {"IRVersion" : "IR50", "server" : "40.dataloader.ionreporter.thermofisher.com",
                "port" : "443", "protocol" : "https"
        }
        IR46 = {"IRVersion" : "IR46", "server" : "40.dataloader.ionreporter.thermofisher.com",
                "port" : "443", "protocol" : "https"
        }
        IR44 = {"IRVersion" : "IR44", "server" : "40.dataloader.ionreporter.thermofisher.com",
                "port" : "443", "protocol" : "https"
        }
        IR42 = {"IRVersion" : "IR42", "server" : "40.dataloader.ionreporter.thermofisher.com",
                "port" : "443", "protocol" : "https"
        }
        IR40 = {"IRVersion" : "IR40", "server" : "40.dataloader.ionreporter.thermofisher.com",
                "port" : "443", "protocol" : "https"
        }
        IR1X = {"IRVersion" : "IR1X", "server" : "dataloader.ionreporter.thermofisher.com",
                "port" : "443", "protocol" : "https"
        }

        versions["urls"].append(IR54)
        versions["urls"].append(IR52)
        versions["urls"].append(IR50)
        versions["urls"].append(IR46)
        versions["urls"].append(IR44)
        versions["urls"].append(IR42)
        versions["urls"].append(IR40)
        versions["urls"].append(IR1X)

        return versions

def versions(bucket):
    if "request_post" in bucket:
        inputJson = {"irAccount": bucket["request_post"]}
        return get_versions(inputJson)
    else:
        return bucket

def details(bucket):
    if "request_post" in bucket:
        inputJson = {"irAccount": bucket["request_post"]}
        return getUserDetails(inputJson)
    else:
        return bucket

def auth(bucket):
    if "request_post" in bucket:
        inputJson = {"irAccount": bucket["request_post"]}
        return authCheck(inputJson)
    else:
        return bucket


def getPermissibleRangeOfNumParallelStreamsValues(bucket):
    # bucket is currently not used, but may be used in future, to generate this list 
    # really based on who the TS or IR user is, what kind of machines they have.
    # as of now it is a constant list, and allows all the possible values of the range.
    #
    # The default has to be empty. If the user didnt choose anything in the manual launch
    # instance page, then there is a logic in place in iru code to arrive at safe values
    # for this, based on IonReporterUploader.properties. That logic will be active only
    # if user has not specified anything. So, if the user did not specify anything, we
    # should not have any values here. 
    numParallelStreamsValues=["1","2","3","4","5"]
    return {"status":"true", "error":"","numParallelStreamsValues":numParallelStreamsValues,"key":"numParallelStreams","descriptionText":"Number of Parallel Streams", "defaultValue":"","defaultLabel":"Default","onMouseOver":""}

def getPermissibleRangeOfFileSegmentSizeValues(bucket):
    # bucket is currently not used, but may be used in future, to generate this list 
    # really based on who the TS or IR user is, what kind of machines they have.
    # as of now it is a constant list, and allows all the possible values of the range.
    #
    # The default has to be empty. If the user didnt choose anything in the manual launch
    # instance page, then there is a logic in place in iru code to arrive at safe values
    # for this, based on IonReporterUploader.properties. That logic will be active only
    # if user has not specified anything. So, if the user did not specify anything, we
    # should not have any values here. 
    fileSegmentSizeValues=["16MB","32MB","64MB","128MB"]   
                     #256MB is possible, but not working out on poor network machines in the field
    return {"status":"true", "error":"","fileSegmentSizeValues":fileSegmentSizeValues, "key":"fileSegmentSize","descriptionText":"File Segment Size","defaultValue":"","defaultLabel":"Default", "onMouseOver":""}



def workflows(bucket):
    user = str(bucket["user"])
    if "request_get" in bucket:
        #get the id from the querystring
        config_id = bucket["request_get"].get("id", False)

        #grab the config blob
        config = bucket.get("config", False)
        all_userconfigs = config.get("userconfigs", False)
        userconfigs = all_userconfigs.get(user)

        #now search for the config with the id given
        for userconfig in userconfigs:
            if userconfig.get("id", False):
                if userconfig.get("id") == config_id:
                    selected = {}
                    selected["irAccount"] = userconfig
                    if "filterKey" in bucket["request_get"]:
                        selected["filterKey"] = bucket["request_get"]["filterKey"]
                    if "filterValue" in bucket["request_get"]:
                        selected["filterValue"] = bucket["request_get"]["filterValue"]
                    if "andFilterKey2" in bucket["request_get"]:
                        selected["andFilterKey2"] = bucket["request_get"]["andFilterKey2"]
                    if "andFilterValue2" in bucket["request_get"]:
                        selected["andFilterValue2"] = bucket["request_get"]["andFilterValue2"]
                    return getWorkflowList(selected)

        #if we got all the way down here it failed
        return False


def workflowsWithOncomine(bucket):      # not likely to be used anymore due to TS UI changes 
    if "request_get" in bucket:
        selectedAccountResult = getSelectedIRAccountFromBucket(bucket)
        if (selectedAccountResult["status"] != "true") :
            return selectedAccountResult
        inputJson = selectedAccountResult["selectedAccount"]
        return getWorkflowListWithOncomine(inputJson)
    return {"status": "false", "error": "request was not a GET"}

def workflowsWithoutOncomine(bucket):
    if "request_get" in bucket:
        selectedAccountResult = getSelectedIRAccountFromBucket(bucket)
        if (selectedAccountResult["status"] != "true") :
            return selectedAccountResult
        inputJson = selectedAccountResult["selectedAccount"]
        return getWorkflowListWithoutOncomine(inputJson)
    return {"status": "false", "error": "request was not a GET"}



def wValidateUserInput(bucket):
    """
    Takes in the config id as a querystring parameter, and the HTTP POST body and passes those to
    validateUserInput
    """
    user = str(bucket["user"])
    if "request_get" in bucket:
        #get the id from the querystring
        config_id = bucket["request_get"].get("id", False)

        #grab the config blob
        config = bucket.get("config", False)
        all_userconfigs = config.get("userconfigs", False)
        userconfigs = all_userconfigs.get(user)
        #now search for the config with the id given
        for userconfig in userconfigs:
            if userconfig.get("id", False):
                if userconfig.get("id") == config_id:
                    selected = {}
                    selected["irAccount"] = userconfig
                    if "filterKey" in bucket["request_get"]:
                        selected["filterKey"] = bucket["request_get"]["filterKey"]
                    if "filterValue" in bucket["request_get"]:
                        selected["filterValue"] = bucket["request_get"]["filterValue"]
                    if "andFilterKey2" in bucket["request_get"]:
                        selected["andFilterKey2"] = bucket["request_get"]["andFilterKey2"]
                    if "andFilterValue2" in bucket["request_get"]:
                        selected["andFilterValue2"] = bucket["request_get"]["andFilterValue2"]
                    #get the http post body (form data)
                    selected["userInput"] = bucket["request_post"]
                    return validateUserInput(selected)

        #if we got all the way down here it failed
        return False

def newWorkflow(bucket):
    user = str(bucket["user"])
    if "request_get" in bucket:
        response = {"status": "false"}

        #get the id from the querystring
        config_id = bucket["request_get"].get("id", False)

        #grab the config blob
        config = bucket.get("config", False)
        all_userconfigs = config.get("userconfigs", False)
        userconfigs = all_userconfigs.get(user)

        #now search for the config with the id given
        for userconfig in userconfigs:
            if userconfig.get("id", False):
                if userconfig.get("id") == config_id:
                    selected = {}
                    version = userconfig["version"]
                    version = version.split("IR")[1]
                    selected["irAccount"] = userconfig
                    if version == '40':
                        response = getWorkflowCreationLandingPageURL(selected)     # token is embedded in the query params
                        response["method"] = "get"
                    else:
                        response = getWorkflowCreationLandingPageURLBase(selected) # no token.. just the base url. the caller has to embed the token in the post data
                        response["method"] = "post"

        #if we got all the way down here it failed
        return response

def userInput(bucket):
    user = str(bucket["user"])
    if "request_get" in bucket:
        #get the id from the querystring
        config_id = bucket["request_get"].get("id", False)

        #grab the config blob
        config = bucket.get("config", False)
        all_userconfigs = config.get("userconfigs", False)
        userconfigs = all_userconfigs.get(user)

        #now search for the config with the id given
        for userconfig in userconfigs:
            if userconfig.get("id", False):
                if userconfig.get("id") == config_id:
                    selected = {}
                    selected["irAccount"] = userconfig
                    if "filterKey" in bucket["request_get"]:
                        selected["filterKey"] = bucket["request_get"]["filterKey"]
                    if "filterValue" in bucket["request_get"]:
                        selected["filterValue"] = bucket["request_get"]["filterValue"]
                    if "andFilterKey2" in bucket["request_get"]:
                        selected["andFilterKey2"] = bucket["request_get"]["andFilterKey2"]
                    if "andFilterValue2" in bucket["request_get"]:
                        selected["andFilterValue2"] = bucket["request_get"]["andFilterValue2"]
                    return getUserInput(selected)

        #if we got all the way down here it failed
        return False


def get_versions(inputJson):
    irAccountJson = inputJson["irAccount"]
    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = getGrwsPath(irAccountJson)

    #curl -ks -H Authorization:rwVcoTeYGfKxItiaWo2lngsV/r0jukG2pLKbZBkAFnlPbjKfPTXLbIhPb47YA9u78 https://xyz.com:443/grws_1_2/data/versionList
    url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/versionList/"
    cmd="curl -ks -3 -H Authorization:"+token+ " " +url
    result = get_httpResponseFromSystemToolsAsJson(cmd)
    if "json" in result:
        result["json"]["account_type"] = getGrwsPath(irAccountJson)

    if (result["status"] =="true"):
        return result["json"]
    cmd="curl -ks -H Authorization:"+token+ " " +url
    result = get_httpResponseFromSystemToolsAsJson(cmd)
    if (result["status"] =="true"):
        return result["json"]
    return result

    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/versionList/"
        hdrs = {'Authorization': token}
        resp = requests.get(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = resp.json()
        else:
        #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        raise Exception("Error Code " + str(e))
    except requests.exceptions.HTTPError, e:
        raise Exception("Error Code " + str(e))
    except requests.exceptions.RequestException, e:
        raise Exception("Error Code " + str(e))
    except Exception, e:
        raise Exception("Error Code " + str(e))
    return result

def getIRCancerTypesList(inputJson):
    irAccountJson = inputJson["irAccount"]
    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    write_debug_log("getting details  ")
    grwsPath = getGrwsPath(irAccountJson)
    write_debug_log("getting details grwsPath "+ grwsPath)

    #curl -ks --request POST -H Authorization:rwVcoTeYGfKxItiaWo2lngsV/r0jukG2pLKbZBkAFnlPbjKfPTXLbIhPb47YA9u78 https://xyz.com:443/grws_1_2/data/getAvailableCancerType
    url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/getAvailableCancerType"
    header=" --header 'Content-Type: application/x-www-form-urlencoded'"
    cmd="curl -ks -3 --request POST -H Authorization:"+token+ " " +url + header
    result = get_httpResponseFromSystemToolsAsJson(cmd)
    if (result["status"] =="true"):
        return {"status":"true", "error":"none", "cancerTypes":result["json"]}
    cmd="curl -ks --request POST -H Authorization:"+token+ " " +url + header
    result = get_httpResponseFromSystemToolsAsJson(cmd)
    if (result["status"] =="true"):
        return {"status":"true", "error":"none", "cancerTypes":result["json"]}
    return result


    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/getAvailableCancerType/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            #result = resp.json()
            #result = json.load(resp.text)
            result = resp.text
        else:
        #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            #raise Exception("IR WebService Error Code " + str(resp.status_code))
            return {"status": "false", "error": str(resp.status_code)}
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}

    list=[ "Bladder Cancer", "Breast Cancer", "Glioblastoma", "Colorectal Cancer", "Endometrial Cancer", "Esophageal Cancer", "Gastric Cancer", "Gastrointestinal Stromal Tumor", "Head and Neck Cancer", "Liver Cancer", "Non-Small Cell Lung Cancer", "Small Cell Lung", "Melanoma", "Mesothelioma", "Osteosarcoma", "Ovarian Cancer", "Pancreatic Cancer", "Prostate Cancer", "Renal Cancer", "Basal Cell Carcinoma", "Soft Tissue Sarcoma", "Testicular Cancer", "Thyroid Cancer" ]
    #return {"status":"true", "error":"none", "cancerTypes":result}
    return {"status":"true", "error":"none", "cancerTypes":result}






def getSampleTabulationRules_4_0(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []

    workflowDict = {"Name": "Workflow", "Order": "1", "Type": "list", "ValueType": "String"}
#    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "Type": "list", "ValueType": "String",
#                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "Order": "2", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict = {"Name": "Gender", "Order": "3", "Type": "list", "ValueType": "String",
                  "Values": ["Male", "Female", "Unknown"]}
    setIDDict = {"Name": "SetID", "Order": "4", "Type": "input", "ValueType": "Integer"}

    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(setIDDict)
    sampleRelationshipDict["columns"].append(relationDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})

    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                                 "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                                 "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female"]}})

    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}



def getSampleTabulationRules_4_2(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    workflowDict = {"Name": "Workflow", "FullName": "Workflow", "Order": "1", "key":"Workflow", "Type": "list", "ValueType": "String"}
#    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "key":"Relation", "Type": "list", "ValueType": "String",
#                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "FullName": "Relation Role", "Order": "2", "key":"RelationRole", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict =   {"Name": "Gender", "FullName": "Gender","Order": "3", "key":"Gender", "Type": "list", "ValueType": "String",
                    "Values": ["Male", "Female", "Unknown"]}
    nucleoDict =   {"Name": "NucleotideType", "FullName": "Nucleotide Type", "Order": "4","key":"NucleotideType",  "Type": "list", "ValueType": "String",
                    "Values": ["DNA", "RNA"]}
    cellPctDict =  {"Name": "CellularityPct", "FullName": "Cellularity Percentage", "Order": "5","key":"cellularityPct",  "Type": "input", 
                "ValueType": "Integer", "Integer.Low":"0", "Integer.High":"100",
                    "ValueDefault":"0"}
    cancerDict =   {"Name": "CancerType", "FullName": "Cancer Type", "Order": "6", "key":"cancerType", "Type": "list", "ValueType": "String",
                    "Values": cancerTypesList}
    setIDDict =    {"Name": "SetID", "FullName": "IR Analysis Set ID", "Order": "7", "key":"setid", "Type": "input", "ValueType": "Integer"}


    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(relationDict)
    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(nucleoDict)
    sampleRelationshipDict["columns"].append(cellPctDict)
    sampleRelationshipDict["columns"].append(cancerDict)
    sampleRelationshipDict["columns"].append(setIDDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})
    restrictionRulesList.append({"ruleNumber":"99", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"98", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "SINGLE_RNA_FUSION"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})

    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"10", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA","RNA"]}})
    restrictionRulesList.append({"ruleNumber":"11", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value":"RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["RNA"]}})
    restrictionRulesList.append({"ruleNumber":"12", "validationType":"error",
                                  "For": {"Name": "DNA_RNA_Workflow", "Value":"DNA"},
                                 "Disabled": {"Name": "NucleotideType"}})
    restrictionRulesList.append({"ruleNumber":"13", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"14", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"15", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"16", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CancerType"}})
    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}


def getSampleTabulationRules_4_4(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    workflowDict = {"Name": "Workflow", "FullName": "Workflow", "Order": "1", "key":"Workflow", "Type": "list", "ValueType": "String"}
#    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "key":"Relation", "Type": "list", "ValueType": "String",
#                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "FullName": "Relation Role", "Order": "2", "key":"RelationRole", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict =   {"Name": "Gender", "FullName": "Gender","Order": "3", "key":"Gender", "Type": "list", "ValueType": "String",
                    "Values": ["Male", "Female", "Unknown"]}
    nucleoDict =   {"Name": "NucleotideType", "FullName": "Nucleotide Type", "Order": "4","key":"NucleotideType",  "Type": "list", "ValueType": "String",
                    "Values": ["DNA", "RNA"]}
    cellPctDict =  {"Name": "CellularityPct", "FullName": "Cellularity Percentage", "Order": "5","key":"cellularityPct",  "Type": "input", 
                "ValueType": "Integer", "Integer.Low":"0", "Integer.High":"100",
                    "ValueDefault":"0"}
    cancerDict =   {"Name": "CancerType", "FullName": "Cancer Type", "Order": "6", "key":"cancerType", "Type": "list", "ValueType": "String",
                    "Values": cancerTypesList}
    setIDDict =    {"Name": "SetID", "FullName": "IR Analysis Set ID", "Order": "7", "key":"setid", "Type": "input", "ValueType": "Integer"}


    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(relationDict)
    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(nucleoDict)
    sampleRelationshipDict["columns"].append(cellPctDict)
    sampleRelationshipDict["columns"].append(cancerDict)
    sampleRelationshipDict["columns"].append(setIDDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})
    restrictionRulesList.append({"ruleNumber":"99", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"98", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "SINGLE_RNA_FUSION"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})

    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"10", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA","RNA"]}})
    restrictionRulesList.append({"ruleNumber":"11", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value":"RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["RNA"]}})
    restrictionRulesList.append({"ruleNumber":"12", "validationType":"error",
                                  "For": {"Name": "DNA_RNA_Workflow", "Value":"DNA"},
                                 "Disabled": {"Name": "NucleotideType"}})
    restrictionRulesList.append({"ruleNumber":"13", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"14", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"15", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"16", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CancerType"}})
    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}


def getSampleTabulationRules_4_6(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    workflowDict = {"Name": "Workflow", "FullName": "Workflow", "Order": "1", "key":"Workflow", "Type": "list", "ValueType": "String"}
#    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "key":"Relation", "Type": "list", "ValueType": "String",
#                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "FullName": "Relation Role", "Order": "2", "key":"RelationRole", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict =   {"Name": "Gender", "FullName": "Gender","Order": "3", "key":"Gender", "Type": "list", "ValueType": "String",
                    "Values": ["Male", "Female", "Unknown"]}
    nucleoDict =   {"Name": "NucleotideType", "FullName": "Nucleotide Type", "Order": "4","key":"NucleotideType",  "Type": "list", "ValueType": "String",
                    "Values": ["DNA", "RNA"]}
    cellPctDict =  {"Name": "CellularityPct", "FullName": "Cellularity Percentage", "Order": "5","key":"cellularityPct",  "Type": "input", 
                "ValueType": "Integer", "Integer.Low":"0", "Integer.High":"100",
                    "ValueDefault":"0"}
    cancerDict =   {"Name": "CancerType", "FullName": "Cancer Type", "Order": "6", "key":"cancerType", "Type": "list", "ValueType": "String",
                    "Values": cancerTypesList}
    setIDDict =    {"Name": "SetID", "FullName": "IR Analysis Set ID", "Order": "7", "key":"setid", "Type": "input", "ValueType": "Integer"}


    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(relationDict)
    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(nucleoDict)
    sampleRelationshipDict["columns"].append(cellPctDict)
    sampleRelationshipDict["columns"].append(cancerDict)
    sampleRelationshipDict["columns"].append(setIDDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})
    restrictionRulesList.append({"ruleNumber":"99", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"98", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "SINGLE_RNA_FUSION"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})

    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"10", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA","RNA"]}})
    restrictionRulesList.append({"ruleNumber":"11", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value":"RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["RNA"]}})
    restrictionRulesList.append({"ruleNumber":"12", "validationType":"error",
                                  "For": {"Name": "DNA_RNA_Workflow", "Value":"DNA"},
                                 "Disabled": {"Name": "NucleotideType"}})
    restrictionRulesList.append({"ruleNumber":"13", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"14", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"15", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"16", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CancerType"}})
    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}


def getSampleTabulationRules_5_0(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    workflowDict = {"Name": "Workflow", "FullName": "Workflow", "Order": "1", "key":"Workflow", "Type": "list", "ValueType": "String"}
#    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "key":"Relation", "Type": "list", "ValueType": "String",
#                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "FullName": "Relation Role", "Order": "2", "key":"RelationRole", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict =   {"Name": "Gender", "FullName": "Gender","Order": "3", "key":"Gender", "Type": "list", "ValueType": "String",
                    "Values": ["Male", "Female", "Unknown"]}
    nucleoDict =   {"Name": "NucleotideType", "FullName": "Nucleotide Type", "Order": "4","key":"NucleotideType",  "Type": "list", "ValueType": "String",
                    "Values": ["DNA", "RNA"]}
    cellPctDict =  {"Name": "CellularityPct", "FullName": "Cellularity Percentage", "Order": "5","key":"cellularityPct",  "Type": "input", 
                "ValueType": "Integer", "Integer.Low":"0", "Integer.High":"100",
                    "ValueDefault":"0"}
    cancerDict =   {"Name": "CancerType", "FullName": "Cancer Type", "Order": "6", "key":"cancerType", "Type": "list", "ValueType": "String",
                    "Values": cancerTypesList}
    setIDDict =    {"Name": "SetID", "FullName": "IR Analysis Set ID", "Order": "7", "key":"setid", "Type": "input", "ValueType": "Integer"}


    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(relationDict)
    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(nucleoDict)
    sampleRelationshipDict["columns"].append(cellPctDict)
    sampleRelationshipDict["columns"].append(cancerDict)
    sampleRelationshipDict["columns"].append(setIDDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})
    restrictionRulesList.append({"ruleNumber":"99", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"98", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "SINGLE_RNA_FUSION"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})

    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"10", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA","RNA"]}})
    restrictionRulesList.append({"ruleNumber":"11", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value":"RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["RNA"]}})
    restrictionRulesList.append({"ruleNumber":"12", "validationType":"error",
                                  "For": {"Name": "DNA_RNA_Workflow", "Value":"DNA"},
                                 "Disabled": {"Name": "NucleotideType"}})
    restrictionRulesList.append({"ruleNumber":"13", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"14", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"15", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"16", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CancerType"}})
    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}

def getSampleTabulationRules_5_2(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    workflowDict = {"Name": "Workflow", "FullName": "Workflow", "Order": "1", "key":"Workflow", "Type": "list", "ValueType": "String"}
#    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "key":"Relation", "Type": "list", "ValueType": "String",
#                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "FullName": "Relation Role", "Order": "2", "key":"RelationRole", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict =   {"Name": "Gender", "FullName": "Gender","Order": "3", "key":"Gender", "Type": "list", "ValueType": "String",
                    "Values": ["Male", "Female", "Unknown"]}
    nucleoDict =   {"Name": "NucleotideType", "FullName": "Nucleotide Type", "Order": "4","key":"NucleotideType",  "Type": "list", "ValueType": "String",
                    "Values": ["DNA", "RNA"]}
    cellPctDict =  {"Name": "CellularityPct", "FullName": "Cellularity Percentage", "Order": "5","key":"cellularityPct",  "Type": "input", 
                "ValueType": "Integer", "Integer.Low":"0", "Integer.High":"100",
                    "ValueDefault":"0"}
    cancerDict =   {"Name": "CancerType", "FullName": "Cancer Type", "Order": "6", "key":"cancerType", "Type": "list", "ValueType": "String",
                    "Values": cancerTypesList}
    setIDDict =    {"Name": "SetID", "FullName": "IR Analysis Set ID", "Order": "7", "key":"setid", "Type": "input", "ValueType": "Integer"}


    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(relationDict)
    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(nucleoDict)
    sampleRelationshipDict["columns"].append(cellPctDict)
    sampleRelationshipDict["columns"].append(cancerDict)
    sampleRelationshipDict["columns"].append(setIDDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})
    restrictionRulesList.append({"ruleNumber":"18", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Father"},
                                  "Valid": {"Name": "Gender", "Values": ["Male"]}})
    restrictionRulesList.append({"ruleNumber":"19", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Mother"},
                                  "Valid": {"Name": "Gender", "Values": ["Female"]}})
    restrictionRulesList.append({"ruleNumber":"20", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Proband"},
                                  "Valid": {"Name": "Gender", "Values": ["Male", "Female"]}})
    restrictionRulesList.append({"ruleNumber":"99", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"98", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "SINGLE_RNA_FUSION"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})

    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"10", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"11", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA","RNA"]}})
    restrictionRulesList.append({"ruleNumber":"12", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value":"RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["RNA"]}})
    restrictionRulesList.append({"ruleNumber":"13", "validationType":"error",
                                  "For": {"Name": "DNA_RNA_Workflow", "Value":"DNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA"]}})
    restrictionRulesList.append({"ruleNumber":"14", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"15", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"16", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"17", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CancerType"}})
    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}



def getSampleTabulationRules_5_4(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    workflowDict = {"Name": "Workflow", "FullName": "Workflow", "Order": "1", "key":"Workflow", "Type": "list", "ValueType": "String"}
#    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "key":"Relation", "Type": "list", "ValueType": "String",
#                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "FullName": "Relation Role", "Order": "2", "key":"RelationRole", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict =   {"Name": "Gender", "FullName": "Gender","Order": "3", "key":"Gender", "Type": "list", "ValueType": "String",
                    "Values": ["Male", "Female", "Unknown"]}
    nucleoDict =   {"Name": "NucleotideType", "FullName": "Nucleotide Type", "Order": "4","key":"NucleotideType",  "Type": "list", "ValueType": "String",
                    "Values": ["DNA", "RNA"]}
    cellPctDict =  {"Name": "CellularityPct", "FullName": "Cellularity Percentage", "Order": "5","key":"cellularityPct",  "Type": "input", 
                "ValueType": "Integer", "Integer.Low":"0", "Integer.High":"100",
                    "ValueDefault":"0"}
    cancerDict =   {"Name": "CancerType", "FullName": "Cancer Type", "Order": "6", "key":"cancerType", "Type": "list", "ValueType": "String",
                    "Values": cancerTypesList}
    setIDDict =    {"Name": "SetID", "FullName": "IR Analysis Set ID", "Order": "7", "key":"setid", "Type": "input", "ValueType": "Integer"}


    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(relationDict)
    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(nucleoDict)
    sampleRelationshipDict["columns"].append(cellPctDict)
    sampleRelationshipDict["columns"].append(cancerDict)
    sampleRelationshipDict["columns"].append(setIDDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})
    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"10", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"11", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA","RNA"]}})
    restrictionRulesList.append({"ruleNumber":"12", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value":"RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["RNA"]}})
    restrictionRulesList.append({"ruleNumber":"13", "validationType":"error",
                                  "For": {"Name": "DNA_RNA_Workflow", "Value":"DNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA"]}})
    restrictionRulesList.append({"ruleNumber":"14", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"15", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"16", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"17", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"18", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Father"},
                                  "Valid": {"Name": "Gender", "Values": ["Male"]}})
    restrictionRulesList.append({"ruleNumber":"19", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Mother"},
                                  "Valid": {"Name": "Gender", "Values": ["Female"]}})
    restrictionRulesList.append({"ruleNumber":"20", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Proband"},
                                  "Valid": {"Name": "Gender", "Values": ["Male", "Female"]}})
    restrictionRulesList.append({"ruleNumber":"21", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"22", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"23", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"24", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"99", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"98", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "SINGLE_RNA_FUSION"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})

    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}


def getSampleTabulationRules_5_6(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    workflowDict = {"Name": "Workflow", "FullName": "Workflow", "Order": "1", "key":"Workflow", "Type": "list", "ValueType": "String"}
#    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "key":"Relation", "Type": "list", "ValueType": "String",
#                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "FullName": "Relation Role", "Order": "2", "key":"RelationRole", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict =   {"Name": "Gender", "FullName": "Gender","Order": "3", "key":"Gender", "Type": "list", "ValueType": "String",
                    "Values": ["Male", "Female", "Unknown"]}
    nucleoDict =   {"Name": "NucleotideType", "FullName": "Nucleotide Type", "Order": "4","key":"NucleotideType",  "Type": "list", "ValueType": "String",
                    "Values": ["DNA", "RNA"]}
    cellPctDict =  {"Name": "CellularityPct", "FullName": "Cellularity Percentage", "Order": "5","key":"cellularityPct",  "Type": "input", 
                "ValueType": "Integer", "Integer.Low":"0", "Integer.High":"100",
                    "ValueDefault":"0"}
    cancerDict =   {"Name": "CancerType", "FullName": "Cancer Type", "Order": "6", "key":"cancerType", "Type": "list", "ValueType": "String",
                    "Values": cancerTypesList}
    setIDDict =    {"Name": "SetID", "FullName": "IR Analysis Set ID", "Order": "7", "key":"setid", "Type": "input", "ValueType": "Integer"}


    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(relationDict)
    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(nucleoDict)
    sampleRelationshipDict["columns"].append(cellPctDict)
    sampleRelationshipDict["columns"].append(cancerDict)
    sampleRelationshipDict["columns"].append(setIDDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})
    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"10", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"11", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA","RNA"]}})
    restrictionRulesList.append({"ruleNumber":"12", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value":"RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["RNA"]}})
    restrictionRulesList.append({"ruleNumber":"13", "validationType":"error",
                                  "For": {"Name": "DNA_RNA_Workflow", "Value":"DNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA"]}})
    restrictionRulesList.append({"ruleNumber":"14", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"15", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"16", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"17", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"18", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Father"},
                                  "Valid": {"Name": "Gender", "Values": ["Male"]}})
    restrictionRulesList.append({"ruleNumber":"19", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Mother"},
                                  "Valid": {"Name": "Gender", "Values": ["Female"]}})
    restrictionRulesList.append({"ruleNumber":"20", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Proband"},
                                  "Valid": {"Name": "Gender", "Values": ["Male", "Female"]}})
    restrictionRulesList.append({"ruleNumber":"21", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"22", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"23", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"24", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"99", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"98", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "SINGLE_RNA_FUSION"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})

    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}


def getSampleTabulationRules_5_10(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    workflowDict = {"Name": "Workflow", "FullName": "Workflow", "Order": "1", "key":"Workflow", "Type": "list", "ValueType": "String"}
#    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "key":"Relation", "Type": "list", "ValueType": "String",
#                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "FullName": "Relation Role", "Order": "2", "key":"RelationRole", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict =   {"Name": "Gender", "FullName": "Gender","Order": "3", "key":"Gender", "Type": "list", "ValueType": "String",
                    "Values": ["Male", "Female", "Unknown"]}
    nucleoDict =   {"Name": "NucleotideType", "FullName": "Nucleotide Type", "Order": "4","key":"NucleotideType",  "Type": "list", "ValueType": "String",
                    "Values": ["DNA", "RNA"]}
    cellPctDict =  {"Name": "CellularityPct", "FullName": "Cellularity Percentage", "Order": "5","key":"cellularityPct",  "Type": "input", 
                "ValueType": "Integer", "Integer.Low":"0", "Integer.High":"100",
                    "ValueDefault":"0"}
    cancerDict =   {"Name": "CancerType", "FullName": "Cancer Type", "Order": "6", "key":"cancerType", "Type": "list", "ValueType": "String",
                    "Values": cancerTypesList}
    setIDDict =    {"Name": "SetID", "FullName": "IR Analysis Set ID", "Order": "7", "key":"setid", "Type": "input", "ValueType": "Integer"}


    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(relationDict)
    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(nucleoDict)
    sampleRelationshipDict["columns"].append(cellPctDict)
    sampleRelationshipDict["columns"].append(cancerDict)
    sampleRelationshipDict["columns"].append(setIDDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})
    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"10", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"11", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA","RNA"]}})
    restrictionRulesList.append({"ruleNumber":"12", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value":"RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["RNA"]}})
    restrictionRulesList.append({"ruleNumber":"13", "validationType":"error",
                                  "For": {"Name": "DNA_RNA_Workflow", "Value":"DNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA"]}})
    restrictionRulesList.append({"ruleNumber":"14", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"15", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"16", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"17", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"18", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Father"},
                                  "Valid": {"Name": "Gender", "Values": ["Male"]}})
    restrictionRulesList.append({"ruleNumber":"19", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Mother"},
                                  "Valid": {"Name": "Gender", "Values": ["Female"]}})
    restrictionRulesList.append({"ruleNumber":"20", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Proband"},
                                  "Valid": {"Name": "Gender", "Values": ["Male", "Female"]}})
    restrictionRulesList.append({"ruleNumber":"21", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"22", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"23", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"24", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"99", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"98", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "SINGLE_RNA_FUSION"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})

    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}


def getSampleTabulationRules_5_12(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    workflowDict = {"Name": "Workflow", "FullName": "Workflow", "Order": "1", "key":"Workflow", "Type": "list", "ValueType": "String"}
#    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "key":"Relation", "Type": "list", "ValueType": "String",
#                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "FullName": "Relation Role", "Order": "2", "key":"RelationRole", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict =   {"Name": "Gender", "FullName": "Gender","Order": "3", "key":"Gender", "Type": "list", "ValueType": "String",
                    "Values": ["Male", "Female", "Unknown"]}
    nucleoDict =   {"Name": "NucleotideType", "FullName": "Nucleotide Type", "Order": "4","key":"NucleotideType",  "Type": "list", "ValueType": "String",
                    "Values": ["DNA", "RNA"]}
    cellPctDict =  {"Name": "CellularityPct", "FullName": "Cellularity Percentage", "Order": "5","key":"cellularityPct",  "Type": "input", 
                "ValueType": "Integer", "Integer.Low":"0", "Integer.High":"100",
                    "ValueDefault":"0"}
    cancerDict =   {"Name": "CancerType", "FullName": "Cancer Type", "Order": "6", "key":"cancerType", "Type": "list", "ValueType": "String",
                    "Values": cancerTypesList}
    setIDDict =    {"Name": "SetID", "FullName": "IR Analysis Set ID", "Order": "7", "key":"setid", "Type": "input", "ValueType": "Integer"}


    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(relationDict)
    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(nucleoDict)
    sampleRelationshipDict["columns"].append(cellPctDict)
    sampleRelationshipDict["columns"].append(cancerDict)
    sampleRelationshipDict["columns"].append(setIDDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})
    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"10", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"11", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA","RNA"]}})
    restrictionRulesList.append({"ruleNumber":"12", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value":"RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["RNA"]}})
    restrictionRulesList.append({"ruleNumber":"13", "validationType":"error",
                                  "For": {"Name": "DNA_RNA_Workflow", "Value":"DNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA"]}})
    restrictionRulesList.append({"ruleNumber":"14", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"15", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"16", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"17", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"18", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Father"},
                                  "Valid": {"Name": "Gender", "Values": ["Male"]}})
    restrictionRulesList.append({"ruleNumber":"19", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Mother"},
                                  "Valid": {"Name": "Gender", "Values": ["Female"]}})
    restrictionRulesList.append({"ruleNumber":"20", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Proband"},
                                  "Valid": {"Name": "Gender", "Values": ["Male", "Female"]}})
    restrictionRulesList.append({"ruleNumber":"21", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"22", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"23", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"24", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"99", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"98", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "SINGLE_RNA_FUSION"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})

    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}

def getSampleTabulationRules_5_14(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    workflowDict = {"Name": "Workflow", "FullName": "Workflow", "Order": "1", "key":"Workflow", "Type": "list", "ValueType": "String"}
#    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "key":"Relation", "Type": "list", "ValueType": "String",
#                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "FullName": "Relation Role", "Order": "2", "key":"RelationRole", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict =   {"Name": "Gender", "FullName": "Gender","Order": "3", "key":"Gender", "Type": "list", "ValueType": "String",
                    "Values": ["Male", "Female", "Unknown"]}
    nucleoDict =   {"Name": "NucleotideType", "FullName": "Nucleotide Type", "Order": "4","key":"NucleotideType",  "Type": "list", "ValueType": "String",
                    "Values": ["DNA", "RNA"]}
    cellPctDict =  {"Name": "CellularityPct", "FullName": "Cellularity Percentage", "Order": "5","key":"cellularityPct",  "Type": "input", 
                "ValueType": "Integer", "Integer.Low":"0", "Integer.High":"100",
                    "ValueDefault":"0"}
    cancerDict =   {"Name": "CancerType", "FullName": "Cancer Type", "Order": "6", "key":"cancerType", "Type": "list", "ValueType": "String",
                    "Values": cancerTypesList}
    setIDDict =    {"Name": "SetID", "FullName": "IR Analysis Set ID", "Order": "7", "key":"setid", "Type": "input", "ValueType": "Integer"}


    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(relationDict)
    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(nucleoDict)
    sampleRelationshipDict["columns"].append(cellPctDict)
    sampleRelationshipDict["columns"].append(cancerDict)
    sampleRelationshipDict["columns"].append(setIDDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})
    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                               "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"10", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"11", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA","RNA"]}})
    restrictionRulesList.append({"ruleNumber":"12", "validationType":"error",
                               "For": {"Name": "DNA_RNA_Workflow", "Value":"RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["RNA"]}})
    restrictionRulesList.append({"ruleNumber":"13", "validationType":"error",
                                  "For": {"Name": "DNA_RNA_Workflow", "Value":"DNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA"]}})
    restrictionRulesList.append({"ruleNumber":"14", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"15", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"16", "validationType":"error",
                                  "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"17", "validationType":"error",
                                  "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"18", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Father"},
                                  "Valid": {"Name": "Gender", "Values": ["Male"]}})
    restrictionRulesList.append({"ruleNumber":"19", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Mother"},
                                  "Valid": {"Name": "Gender", "Values": ["Female"]}})
    restrictionRulesList.append({"ruleNumber":"20", "validationType":"error",
                               "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Proband"},
                                  "Valid": {"Name": "Gender", "Values": ["Male", "Female"]}})
    restrictionRulesList.append({"ruleNumber":"21", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"22", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"23", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"24", "validationType":"error",
                               "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"99", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"98", "validationType":"error",            # a tempporary rule that is going to go away.
                               "For": {"Name": "RelationshipType", "Value": "SINGLE_RNA_FUSION"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})

    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}

def getSampleTabulationRules_5_16(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    workflowDict = {"Name": "Workflow", "FullName": "Workflow", "Order": "1", "key":"Workflow", "Type": "list", "ValueType": "String"}
    #    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "key":"Relation", "Type": "list", "ValueType": "String",
    #                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "FullName": "Relation Role", "Order": "2", "key":"RelationRole", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict =   {"Name": "Gender", "FullName": "Gender","Order": "3", "key":"Gender", "Type": "list", "ValueType": "String",
                    "Values": ["Male", "Female", "Unknown"]}
    nucleoDict =   {"Name": "NucleotideType", "FullName": "Nucleotide Type", "Order": "4","key":"NucleotideType",  "Type": "list", "ValueType": "String",
                    "Values": ["DNA", "RNA"]}
    cellPctDict =  {"Name": "CellularityPct", "FullName": "Cellularity Percentage", "Order": "5","key":"cellularityPct",  "Type": "input",
                    "ValueType": "Integer", "Integer.Low":"0", "Integer.High":"100",
                    "ValueDefault":"0"}
    cancerDict =   {"Name": "CancerType", "FullName": "Cancer Type", "Order": "6", "key":"cancerType", "Type": "list", "ValueType": "String",
                    "Values": cancerTypesList}
    setIDDict =    {"Name": "SetID", "FullName": "IR Analysis Set ID", "Order": "7", "key":"setid", "Type": "input", "ValueType": "Integer"}


    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(relationDict)
    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(nucleoDict)
    sampleRelationshipDict["columns"].append(cellPctDict)
    sampleRelationshipDict["columns"].append(cancerDict)
    sampleRelationshipDict["columns"].append(setIDDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})
    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                                 "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                                 "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"10", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"11", "validationType":"error",
                                 "For": {"Name": "DNA_RNA_Workflow", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA","RNA"]}})
    restrictionRulesList.append({"ruleNumber":"12", "validationType":"error",
                                 "For": {"Name": "DNA_RNA_Workflow", "Value":"RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["RNA"]}})
    restrictionRulesList.append({"ruleNumber":"13", "validationType":"error",
                                 "For": {"Name": "DNA_RNA_Workflow", "Value":"DNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA"]}})
    restrictionRulesList.append({"ruleNumber":"14", "validationType":"error",
                                 "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"15", "validationType":"error",
                                 "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"16", "validationType":"error",
                                 "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"17", "validationType":"error",
                                 "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"18", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male"]}})
    restrictionRulesList.append({"ruleNumber":"19", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female"]}})
    restrictionRulesList.append({"ruleNumber":"20", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Proband"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Female"]}})
    restrictionRulesList.append({"ruleNumber":"21", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"22", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"23", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"24", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"99", "validationType":"error",            # a tempporary rule that is going to go away.
                                 "For": {"Name": "RelationshipType", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"98", "validationType":"error",            # a tempporary rule that is going to go away.
                                 "For": {"Name": "RelationshipType", "Value": "SINGLE_RNA_FUSION"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})

    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}

def getSampleTabulationRules_5_18(inputJson, workflowFullDetail):
    sampleRelationshipDict = {}
    sampleRelationshipDict["column-map"] = workflowFullDetail
    sampleRelationshipDict["columns"] = []
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    workflowDict = {"Name": "Workflow", "FullName": "Workflow", "Order": "1", "key":"Workflow", "Type": "list", "ValueType": "String"}
    #    relationshipTypeDict = {"Name": "RelationshipType", "Order": "3", "key":"Relation", "Type": "list", "ValueType": "String",
    #                            "Values": ["Self", "Tumor_Normal", "Sample_Control", "Trio"]}
    relationDict = {"Name": "Relation", "FullName": "Relation Role", "Order": "2", "key":"RelationRole", "Type": "list", "ValueType": "String",
                    "Values": ["Sample", "Control", "Tumor", "Normal", "Father", "Mother", "Proband", "Self"]}
    genderDict =   {"Name": "Gender", "FullName": "Gender","Order": "3", "key":"Gender", "Type": "list", "ValueType": "String",
                    "Values": ["Male", "Female", "Unknown"]}
    nucleoDict =   {"Name": "NucleotideType", "FullName": "Nucleotide Type", "Order": "4","key":"NucleotideType",  "Type": "list", "ValueType": "String",
                    "Values": ["DNA", "RNA"]}
    cellPctDict =  {"Name": "CellularityPct", "FullName": "Cellularity Percentage", "Order": "5","key":"cellularityPct",  "Type": "input",
                    "ValueType": "Integer", "Integer.Low":"0", "Integer.High":"100",
                    "ValueDefault":"0"}
    cancerDict =   {"Name": "CancerType", "FullName": "Cancer Type", "Order": "6", "key":"cancerType", "Type": "list", "ValueType": "String",
                    "Values": cancerTypesList}
    setIDDict =    {"Name": "SetID", "FullName": "IR Analysis Set ID", "Order": "7", "key":"setid", "Type": "input", "ValueType": "Integer"}


    workflowDictValues = []
    for entry in workflowFullDetail :
        workflowName = entry["Workflow"]
        workflowDictValues.append(workflowName)
    workflowDict["Values"] = workflowDictValues

    sampleRelationshipDict["columns"].append(workflowDict)
    #sampleRelationshipDict["columns"].append(relationshipTypeDict)
    sampleRelationshipDict["columns"].append(relationDict)
    sampleRelationshipDict["columns"].append(genderDict)
    sampleRelationshipDict["columns"].append(nucleoDict)
    sampleRelationshipDict["columns"].append(cellPctDict)
    sampleRelationshipDict["columns"].append(cancerDict)
    sampleRelationshipDict["columns"].append(setIDDict)

    restrictionRulesList = []
    #restrictionRulesList.append({"ruleNumber":"1", "validationType":"error","For":{"Name": "RelationShipType", "Value":"Self"}, "Disabled":{"Name":"SetID"}})
    #restrictionRulesList.append({"ruleNumber":"2", "validationType":"error","For": {"Name": "RelationShipType", "Value": "Self"}, "Disabled": {"Name": "Relation"}})
    restrictionRulesList.append({"ruleNumber":"3", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Self"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"4", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Tumor_Normal"},
                                 "Valid": {"Name": "Relation", "Values": ["Tumor", "Normal"]}})
    restrictionRulesList.append({"ruleNumber":"5", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Sample_Control"},
                                 "Valid": {"Name": "Relation", "Values": ["Sample", "Control"]}})
    restrictionRulesList.append({"ruleNumber":"6", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "Valid": {"Name": "Relation", "Values": ["Father", "Mother", "Proband"]}})
    restrictionRulesList.append({"ruleNumber":"7", "validationType":"error",
                                 "For": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"8", "validationType":"error",
                                 "For": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female", "Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"9", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "METAGENOMICS"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"10", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Gender", "Values": ["Unknown"]}})
    restrictionRulesList.append({"ruleNumber":"11", "validationType":"error",
                                 "For": {"Name": "DNA_RNA_Workflow", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA","RNA"]}})
    restrictionRulesList.append({"ruleNumber":"12", "validationType":"error",
                                 "For": {"Name": "DNA_RNA_Workflow", "Value":"RNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["RNA"]}})
    restrictionRulesList.append({"ruleNumber":"13", "validationType":"error",
                                 "For": {"Name": "DNA_RNA_Workflow", "Value":"DNA"},
                                 "Valid": {"Name": "NucleotideType", "Values": ["DNA"]}})
    restrictionRulesList.append({"ruleNumber":"14", "validationType":"error",
                                 "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"15", "validationType":"error",
                                 "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"0"},
                                 "Disabled": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"16", "validationType":"error",
                                 "For": {"Name": "CELLULARITY_PCT_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CellularityPct"}})
    restrictionRulesList.append({"ruleNumber":"17", "validationType":"error",
                                 "For": {"Name": "CANCER_TYPE_REQUIRED", "Value":"1"},
                                 "NonEmpty": {"Name": "CancerType"}})
    restrictionRulesList.append({"ruleNumber":"18", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Father"},
                                 "Valid": {"Name": "Gender", "Values": ["Male"]}})
    restrictionRulesList.append({"ruleNumber":"19", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Mother"},
                                 "Valid": {"Name": "Gender", "Values": ["Female"]}})
    restrictionRulesList.append({"ruleNumber":"20", "validationType":"error",
                                 "For": {"Name": "RelationshipType", "Value": "Trio"},
                                 "AndFor": {"Name": "Relation", "Value": "Proband"},
                                 "Valid": {"Name": "Gender", "Values": ["Male", "Female"]}})
    restrictionRulesList.append({"ruleNumber":"21", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"22", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "Metagenomics"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"23", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "RelationshipType", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"24", "validationType":"error",
                                 "For": {"Name": "ApplicationType", "Value": "ImmuneRepertoire"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"99", "validationType":"error",            # a tempporary rule that is going to go away.
                                 "For": {"Name": "RelationshipType", "Value": "DNA_RNA"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})
    restrictionRulesList.append({"ruleNumber":"98", "validationType":"error",            # a tempporary rule that is going to go away.
                                 "For": {"Name": "RelationshipType", "Value": "SINGLE_RNA_FUSION"},
                                 "Valid": {"Name": "Relation", "Values": ["Self"]}})

    sampleRelationshipDict["restrictionRules"] = restrictionRulesList
    #return sampleRelationshipDict
    return {"status": "true", "error": "none", "sampleRelationshipsTableInfo": sampleRelationshipDict}


def getUserInput(inputJson):
    irAccountJson = inputJson["irAccount"]
    server = irAccountJson["server"]
    token = irAccountJson["token"]
    protocol = irAccountJson["protocol"]
    port = irAccountJson["port"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"
    #if version == "40" :
    #   grwsPath="grws_4_0"

    workflowsCallResult = getWorkflowList(inputJson)
    if workflowsCallResult.get("status") == "false":
        return {"status": "false", "error": workflowsCallResult.get("error")}
    workflowFullDetail = []
    if "userWorkflows" in workflowsCallResult:
        workflowFullDetail = workflowsCallResult.get("userWorkflows")

    # add Upload Only option
    workflowFullDetail.insert(0,{'ApplicationType':'UploadOnly', 'Workflow':'Upload Only', 'RelationshipType': 'Self'})

    if version == "40":
        return getSampleTabulationRules_4_0(inputJson, workflowFullDetail)
    elif version == "42":
        return getSampleTabulationRules_4_2(inputJson, workflowFullDetail)
    elif version == "44":
        return getSampleTabulationRules_4_4(inputJson, workflowFullDetail)
    elif version == "46":
        return getSampleTabulationRules_4_6(inputJson, workflowFullDetail)
    elif version == "50":
        return getSampleTabulationRules_5_0(inputJson, workflowFullDetail)
    elif version == "52":
        return getSampleTabulationRules_5_2(inputJson, workflowFullDetail)
    elif version == "54":
        return getSampleTabulationRules_5_4(inputJson, workflowFullDetail)
    elif version == "56":
        return getSampleTabulationRules_5_6(inputJson, workflowFullDetail)
    elif version == "510":
        return getSampleTabulationRules_5_10(inputJson, workflowFullDetail)
    elif version == "512":
        return getSampleTabulationRules_5_12(inputJson, workflowFullDetail)
    elif version == "514":
        return getSampleTabulationRules_5_14(inputJson, workflowFullDetail)
    elif version == "516":
        return getSampleTabulationRules_5_16(inputJson, workflowFullDetail)
    elif version == "518":
        return getSampleTabulationRules_5_18(inputJson, workflowFullDetail)
    else:
        return getSampleTabulationRules_5_18(inputJson, workflowFullDetail)



def authCheck(inputJson):
    irAccountJson = inputJson["irAccount"]
    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    if not "account_type" in irAccountJson:
        irAccountJson["account_type"] = "ir"

    grwsPath = getGrwsPath(irAccountJson)
    #curl -ks -H Authorization:rwVcoTeYGfKxItiaWo2lngsV/r0jukG2pLKbZBkAFnlPbjKfPTXLbIhPb47YA9u78 https://xyz.com:443/grws_1_2/usr/authcheck
    url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/usr/authcheck"
    cmd="curl -ks -3 -H Authorization:"+token+ " " +url
    result = get_httpResponseFromSystemTools(cmd)
    if (   (result["status"] =="true")  and (result["stdout"] == "SUCCESS")   ):
        return {"status": "true", "error": "none"}
    cmd="curl -ks -H Authorization:"+token+ " " +url
    result = get_httpResponseFromSystemTools(cmd)
    if (   (result["status"] =="true")  and (result["stdout"] == "SUCCESS")   ):
        return {"status": "true", "error": "none"}
    return result


    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/usr/authcheck/"
        hdrs = {'Authorization': token}
        resp = requests.get(url, verify=False, headers=hdrs, timeout=30)  #timeout is in seconds
        result = ""
        if resp.status_code == requests.codes.ok:          # status_code returns an int
            result = resp.text
        else:
        #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            return {"status": "false", "error": "IR WebService Error Code " + str(resp.status_code)}
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e.code))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e.code))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e.code))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e.code))
        #return {"status":"false", "error":str(e.message)}
        return {"status": "false", "error": str(e)}
    if result == "SUCCESS":
        return {"status": "true", "error": "none"}
    return {"status": "false", "error": "none"}


def getWorkflowList(inputJson):
    irAccountJson = inputJson["irAccount"]
    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = getGrwsPath(irAccountJson)


    try:

        # IR Api internally refers to ionreportermanager/server/workflowSampleAttributeMapping.json on the IR
        #curl -ks -H Authorization:rwVcoTeYGfKxItiaWo2lngsV/r0jukG2pLKbZBkAFnlPbjKfPTXLbIhPb47YA9u78 -H Version:42 https://xyz.com:443/grws_1_2/data/workflowList
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/workflowList"
        result = {}
        returnJson = []
        cmd="curl -ks -3  -H Authorization:"+token  +   " -H Version:"+version   +   " "+url
        cmdResult = get_httpResponseFromSystemToolsAsJson(cmd)
        if (cmdResult["status"] !="true"):
            cmd="curl -ks -H Authorization:"+token  +   " -H Version:"+version   +   " "+url
            cmdResult = get_httpResponseFromSystemToolsAsJson(cmd)
            if (cmdResult["status"] !="true"):
                return cmdResult

        result = cmdResult["json"]
        if type(result) is dict :
            status = result["status"]
            if (status != "200") :
                return {"status": "true",
                        "error": result["message"]
                        }
        # TBD quick fix on indent, with (if True:). need to back indent this block and remove this  (if True:) thing
        if True: 
            try:
              for workflowBlob in result:
                appType = str (workflowBlob.get("ApplicationType"))

                # populate the relation roles type based on specific patterns of application type
                if appType.find("Genetic Disease") != -1  :
                    workflowBlob["RelationshipType"] = "Trio"
                elif appType.find("Tumor Normal") != -1 :
                    workflowBlob["RelationshipType"] = "Tumor_Normal"
                elif appType.find("Paired Sample") != -1 :
                    workflowBlob["RelationshipType"] = "Sample_Control"
                else:
                    workflowBlob["RelationshipType"] = "Self"

                # for metagenomics, multiple records with the same type of roles are allowed
                #if appType.find("METAGENOMICS") != -1  :
                #if (    (appType.find("METAGENOMICS") != -1)   or   (appType.find("Metagenomics") != -1)  )  :
                if (  appType.upper() == "METAGENOMICS"   ) :
                    if "AllowMultipleRoleRecords" not in workflowBlob:
                       workflowBlob["AllowMultipleRoleRecords"] = "true"
                
                #ImmuneRepertoire
                if (  appType.upper() == "IMMUNEREPERTOIRE"   ) :
                    if "AllowMultipleRoleRecords" not in workflowBlob:
                       workflowBlob["AllowMultipleRoleRecords"] = "true"

                # populate the ocp enabled workflow or not
                if "OCP_Workflow" not in workflowBlob :
                    workflowBlob["OCP_Workflow"] = "false"
                    # covers IR46
                    if "tag_Oncomine" in workflowBlob :
                        workflowBlob["OCP_Workflow"] = "true"
                    else:
                        # covers IR42, IR44, IR46       for custom workflows containing oncomine plugin
                        for k in workflowBlob :
                            if k.startswith("wfl_plugin_Oncomine"):
                                workflowBlob["OCP_Workflow"] = "true"
                                break
                    # covers IR42 IR44    DNA_RNA and RNA
                    if workflowBlob["OCP_Workflow"] == "false":
                        #if appType.find("Oncomine") != -1 :
                        if (   (  version in ["40","42","44"]  )   and    (appType.find("Oncomine") != -1)   ) :
                            workflowBlob["OCP_Workflow"] = "true"
                        # covers IR42 IR44    DNA     A bad way, but no other way.
                        elif (  (  version in ["40","42","44"]   )  and   ((appType == "Amplicon Low Frequency Sequencing")  or  (appType == "Annotation"))    ):
                            workflowBlob["OCP_Workflow"] = "true"
                    # safely remove the other type from the list, becuase both of these types are mutually exclusive in nature. 
                    if "tag_ColonLung" in workflowBlob :
                        workflowBlob["OCP_Workflow"] = "false"

                # populate the onconet enabled workflow or not
                if "Onconet_Workflow" not in workflowBlob :
                    workflowBlob["Onconet_Workflow"] = "false"
                    # no way to recognize before IR46
                    # recognizable only from IR46
                    if "tag_ColonLung" in workflowBlob :
                        workflowBlob["Onconet_Workflow"] = "true"
                    #elif (  (version in ["40","42","44"] )   and    (appType.find("Oncomine") != -1)   ) :
                    elif appType.find("Oncomine") != -1 :
                        workflowBlob["Onconet_Workflow"] = "true"
                    #elif (  (version in ["40","42","44"])  and   ((appType == "Amplicon Low Frequency Sequencing")   )    ):
                    elif appType == "Amplicon Low Frequency Sequencing":
                        workflowBlob["Onconet_Workflow"] = "true"
                    # safely remove the other type from the list, becuase both of these types are mutually exclusive in nature. 
                    if "tag_Oncomine" in workflowBlob :
                        workflowBlob["Onconet_Workflow"] = "false"
                    for k in workflowBlob :
                        if k.startswith("wfl_plugin_Oncomine"):
                            workflowBlob["Onconet_Workflow"] = "false"


                if ("tag_DNA" in workflowBlob and workflowBlob["tag_DNA"] == "true") and ("tag_RNA" in workflowBlob and workflowBlob["tag_RNA"] == "true"):
                    workflowBlob["DNA_RNA_Workflow"] = "DNA_RNA"
                elif "tag_DNA" in workflowBlob and workflowBlob["tag_DNA"] == "true":
                    workflowBlob["DNA_RNA_Workflow"] = "DNA"
                elif "tag_RNA" in workflowBlob and workflowBlob["tag_RNA"] == "true":
                    workflowBlob["DNA_RNA_Workflow"] = "RNA"

                # populate the whether DNA/RNA type workflow
                if "DNA_RNA_Workflow" not in workflowBlob :
                    if appType.find("DNA_RNA") != -1 :
                        workflowBlob["DNA_RNA_Workflow"] = "DNA_RNA"
                    elif appType.find("RNA") != -1 :
                        workflowBlob["DNA_RNA_Workflow"] = "RNA"
                    else:
                        workflowBlob["DNA_RNA_Workflow"] = "DNA"


                if (workflowBlob["DNA_RNA_Workflow"] == "RNA"):
                    workflowBlob["CELLULARITY_PCT_REQUIRED"] = "0";


                # A temporary overriding for 4.2. Should go away.
                # The original relationship type should be preserved.
                # Should go away when the TS planning page dynamism is
                # correctly built based on the restriction rules.
                if workflowBlob["DNA_RNA_Workflow"] == "DNA_RNA" :
                    workflowBlob["RelationshipType"] = "DNA_RNA"
                if workflowBlob["DNA_RNA_Workflow"] == "RNA" :
                    workflowBlob["RelationshipType"] = "SINGLE_RNA_FUSION"

                if (  appType.upper() == "IMMUNEREPERTOIRE"   ) :
                    workflowBlob["RelationshipType"] = "Self"

                # In TS when Research Application type is selected as DNA and Target Technique is selected as AmpliSeqHD-DNA,
                # this returns AmpliSeqHD Single Library related workflows too.
                # The below condition will avoid returning Single library workflows.
                if (  appType.upper() == "AMPLISEQHD SINGLE POOL"  ) :
                    workflowBlob["ApplicationType"] = appType.replace(" ", "_")
                    workflowBlob["DNA_RNA_Workflow"] = "DNA"

                keyPairExists=False
                andKeyPair2Exists=False
                atleastOneKeyPairExists=False
                if (  ("filterKey" in inputJson ) and ("filterValue" in inputJson )  ):
                    keyPairExists=True
                    atleastOneKeyPairExists=True
                if (  ("andFilterKey2" in inputJson ) and ("andFilterValue2" in inputJson )  ):
                    andKeyPair2Exists=True
                    atleastOneKeyPairExists=True

                if  atleastOneKeyPairExists==True:   # should go through the filteration. else return all..
                    qualifyFilteration=True
                    if keyPairExists:
                        if (workflowBlob.get(inputJson["filterKey"], None) !=  inputJson["filterValue"])  :
                            qualifyFilteration=False
                    if andKeyPair2Exists:
                        if (workflowBlob.get(inputJson["andFilterKey2"], None) !=  inputJson["andFilterValue2"])  :
                            qualifyFilteration=False
                    if qualifyFilteration==True:
                        returnJson.append (workflowBlob)
                else:
                    returnJson.append (workflowBlob)
            except Exception, a:
               return {"status": "false", "error": str(a)}
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "userWorkflows": returnJson}


def getWorkflowListWithOncomine(inputJson):
    allWorkflowListResult = getWorkflowList(inputJson)
    if (allWorkflowListResult["status"] != "true"):
        return allWorkflowListResult
    allWorkflowList = allWorkflowListResult["userWorkflows"]
    result = []
    for w in allWorkflowList:
        if (w["OCP_Workflow"] == "true" ):
            result.append(w)
    return {"status": "true", "error": "none", "userWorkflows": result}


def getWorkflowListWithoutOncomine(inputJson):
    allWorkflowListResult = getWorkflowList(inputJson)
    if (allWorkflowListResult["status"] != "true"):
        return allWorkflowListResult
    allWorkflowList = allWorkflowListResult["userWorkflows"]
    result = []
    for w in allWorkflowList:
        if (w["OCP_Workflow"] == "false" ):
            result.append(w)
    return {"status": "true", "error": "none", "userWorkflows": result}



def getUserDataUploadPath(inputJson):
    irAccountJson = inputJson["irAccount"]
    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"
    #if version == "40" :
    #   grwsPath="grws"

    #curl -ks -H Authorization:rwVcoTeYGfKxItiaWo2lngsV/r0jukG2pLKbZBkAFnlPbjKfPTXLbIhPb47YA9u78 https://xyz.com:443/grws_1_2/data/uploadpath
    url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/uploadpath/"
    cmd="curl -ks -3    -H Authorization:"+token  +   " -H Version:"+version   +   " "+url
    result = get_httpResponseFromSystemTools(cmd)
    if (result["status"] =="true"):
        return {"status": "true", "error": "none", "userDataUploadPath": result["stdout"]}
    cmd="curl -ks -H Authorization:"+token  +   " -H Version:"+version   +   " "+url
    result = get_httpResponseFromSystemTools(cmd)
    if (result["status"] =="true"):
        return {"status": "true", "error": "none", "userDataUploadPath": result["stdout"]}
    return result



    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/uploadpath/"
        hdrs = {'Authorization': token}
        resp = requests.get(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = ""
        if resp.status_code == requests.codes.ok:
            result = resp.text
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "userDataUploadPath": result}


def sampleExistsOnIR(inputJson):
    sampleName = inputJson["sampleName"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"
    #if version == "40" :
    #   grwsPath="grws"


    #curl -ks --request POST -H Authorization:rwVcoTeYGfKxItiaWo2lngsV/r0jukG2pLKbZBkAFnlPbjKfPTXLbIhPb47YA9u78 -H Version:42 https://xyz.com:443/grws_1_2/data/sampleExists?sampleName=xyz
    url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/sampleExists"
    cmd="curl -ks -3  --request POST -H Authorization:"+token  +   " -H Version:"+version   +   " "+url  + "?sampleName="+sampleName
    result = get_httpResponseFromSystemTools(cmd)
    if (result["status"] !="true"):
        cmd="curl -ks --request POST -H Authorization:"+token  +   " -H Version:"+version   +   " "+url  + "?sampleName="+sampleName
        result = get_httpResponseFromSystemTools(cmd)
        if (result["status"] !="true"):
            return result

    if (result["stdout"] =="true"):
        return {"status": "true", "error": "none"}
    else:
        return {"status": "false", "error": "none"}


    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/sampleExists/"
        hdrs = {'Authorization': token}
        queryArgs = {"sampleName": sampleName}
        resp = requests.post(url, params=queryArgs, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = ""
        if resp.status_code == requests.codes.ok:
            result = resp.text
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    if result == "true":
        return {"status": "true", "error": "none"}
    else:
        return {"status": "false", "error": "none"}


def getUserDetails(inputJson):
    """give it the account dict in, get the token and other info out"""
    write_debug_log("getting details  "+ __file__ + "    " + os.path.dirname(__file__))
    irAccountJson = inputJson["irAccount"]
    userId = irAccountJson["userid"]
    password = irAccountJson["password"]

    protocol = irAccountJson["protocol"]
    name = irAccountJson["name"]

    server = irAccountJson["server"]
    port = irAccountJson["port"]
    #token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    accountType = irAccountJson["account_type"]
    write_debug_log("getUserDetails:"+ accountType)
    grwsPath = getGrwsPath(irAccountJson)

    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "false", "error": "User Details Query not supported for this version of IR " + version,
                "details": {}}

    if not name:
        return {"status":"false","error":"Empty display name found", "details":{}}

    if not server:
        return {"status":"false","error":"Empty server address found", "details":{}}

    if not port:
        return {"status":"false","error":"Empty port address found", "details":{}}

    if not (1 <= int(port) <= 65535):
        return {"status":"false","error":"Port number invalid", "details":{}}

    if not userId:
        return {"status":"false","error":"Empty username found", "details":{}}


    if not password:
        return {"status":"false","error":"Empty password found", "details":{}}

    if not server:
        return {"status":"false","error":"Empty server address found", "details":{}}

    encodedPassword=base64.b64encode(password)
    #write_debug_log("encoded password is "+encodedPassword)

    result= get_httpResponseFromIRUJavaAsJson("-u " + userId + " -w " + encodedPassword + " -p "+ protocol + " -a " + server + " -x " + port + " -v " + version + " -c " + "'" + accountType + "'" +" -o userDetails")
    if "json" in result:
        jsondata=result["json"];
        if "eulaAccepted" in jsondata:
            eula=jsondata["eulaAccepted"]
            if eula == "false":
                 return {"status": "false", "error": "Invalid user : EULA not accepted on the IonReporter Software", "details": {}}

    if "json" in result:
        jsondata=result["json"];
        if "userStatus" in jsondata:
            userStatus=jsondata["userStatus"]
            if userStatus != "ENABLED":
                 return {"status": "false", "error": "Invalid user status : User "+userStatus, "details": {}}

    if "json" in result:
        result["json"]["account_type"] = getGrwsPath(irAccountJson)

    if "status" in result:
        if (result["status"] == "true") :
            if "json" in result:
                #first check if any double embedded json like :
                # {"details": {"message": "Invalid credentials. Please recheck the 
                #     username and password", "status": "false"}, "error": "none", "status": "true"}
                if (("status" in result["json"])  and ("message" in result["json"])):
                    return {"status": result["json"]["status"], "error": result["json"]["message"]}
                else:
                    return {"status": "true", "error": "none", "details": result["json"]}
    #return {"status": "false", "error":  result["error"]}
    return result

    ## to be deleted later, if all goes well... 
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/getUserDetails/"
        formParams = {"userName": userId, "password": password}
        #hdrs = {'Authorization':token}
        #resp = requests.post(url,data=formParams,verify=False, headers=hdrs)
        resp = requests.post(url, verify=False, data=formParams, timeout=4)
        result = {}
        if resp.status_code == requests.codes.ok:
            #result = json.loads(resp.text)
            result = resp.json()
        else:
            #raise Exception("IR WebService Error Code " + str(resp.status_code))
            return {"status": "false", "error": "IonReporter Error Status " + str(resp.status_code)}
    except requests.exceptions.ConnectionError, e:
        protocol_error = False
        if "BadStatusLine" in str(e):
            protocol_error = True
        return {"status": "false", "error": "Connection", "protocol_error" : protocol_error}
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.HTTPError, e:
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        return {"status": "false", "error": str(e)}
    except ValueError, e:                                 #json conversion error. just send text as such, even if empty
        return {"status": "false", "error": resp.text}
    except Exception, e:
        return {"status": "false", "error": str(e)}
    if isinstance(result, basestring):
        return {"status": "false", "error": result}
    if "status" in result:
        if result["status"] == "false":
            if "error" in result:
                return {"status": "false", "error": result["error"]}
            else :
                return {"status": "false", "error": "unknown error in getting user info"}
    return {"status": "true", "error": "none", "details": result}


def validateUserInput(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]
    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"
    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    #write_debug_log(userInput)

    if version == "40":
        return validateUserInput_4_0(inputJson)
    elif version == "42":
        return validateUserInput_4_2(inputJson)
    elif version == "44":
        return validateUserInput_4_4(inputJson)
    elif version == "46":
        return validateUserInput_4_6(inputJson)
    elif version == "50":
        return validateUserInput_5_0(inputJson)
    elif version == "52":
        return validateUserInput_5_2(inputJson)
    elif version == "54":
        return validateUserInput_5_4(inputJson)
    elif version == "56":
        return validateUserInput_5_6(inputJson)
    elif version == "510":
        return validateUserInput_5_10(inputJson)
    elif version == "512":
        return validateUserInput_5_12(inputJson)
    elif version == "514":
        return validateUserInput_5_14(inputJson)
    elif version == "516":
        return validateUserInput_5_16(inputJson)
    elif version == "518":
        return validateUserInput_5_18(inputJson)
    return {"status": "false",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}


def validateUserInput_4_0(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"
    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}


    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []
    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
       currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
       orderedColumns[col["Order"]] = col

    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """ 


    ###################################### This is a mock logic. This is not the real validation code. This is for test only 
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
               resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]

    requiresVariantCallerPlugin = False
    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
           uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets
        if  rowStr not in rowErrors:
           rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
           rowWarnings[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"]= uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"]= uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"]= uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if  uip["Workflow"] != "":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
            else:
                uip["ApplicationType"] = "unknown"
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""

        if  uip["NucleotideType"] == "RNA":
            msg="NucleotideType "+ uip["NucleotideType"] + " is not supported for IR 4.0 user accounts"
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            continue

        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = rowStr
        else:
            existingRowStr= uniqueSamples[uip["sample"]]
            msg="sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+existingRowStr+". Please change the sample name"
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)


        # if workflow is empty then dont validate and dont include this row in setid for further validations.
        if uip["Workflow"] == "":
            continue

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            continue
        # save the record on the setID
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[] 
            setidHash[setid]["firstWorkflow"]=uip["Workflow"]
            setidHash[setid]["firstRecordRow"]=uip["row"]
        else:
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            previousRow = setidHash[setid]["firstRecordRow"]
            if expectedWorkflow != uip["Workflow"]:
                msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
        setidHash[setid]["records"].append(uip)



        # check if workflow is still active.
        if uip["Workflow"] not in currentlyAvaliableWorkflows:
            msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time"
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            continue

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"]= uip["sample"]
        sampleExistsCallResults = sampleExistsOnIR(inputJson)
        if sampleExistsCallResults.get("error") != "":
            if sampleExistsCallResults.get("status") == "true":
                msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)

        # check the rules.. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_4_0(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings)

        row = row + 1


    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the corresponding records
        rowsLooked = ""
        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. Please check row(s) " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)

            # check the number of records expected and number of records provided.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            sizeOfAvailableRoles = len(setidHash[setid]["records"])
            if (sizeOfAvailableRoles > sizeOfRequiredRoles):
                msg="For workflow " + setidHash[setid]["firstWorkflow"] +", more than the required number of RelationRoles are found. Expected number of roles is "+ str(sizeOfRequiredRoles) + ". Please check row(s) " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)


        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."





    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
           for e in  rowErrors[rowstr]:
              foundAtLeastOneError =1
              emsg = emsg + e + " ; "
        if rowstr in rowWarnings:
           for w in  rowWarnings[rowstr]:
              wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        validationResults.append(k)

    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin


    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
           "conditions": conditions
           }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """

def validateAllRulesOnRecord_4_0(rules, uip, setidHash, rowErrors, rowWarnings):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]
                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    if uip[kFor] == vFor :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]
                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if uip[kFor] == vFor :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
            elif "Disabled" in rule:
                pass
            else:
                 msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                 inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)


def validateUserInput_4_2(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"
    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []
    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
       currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
       orderedColumns[col["Order"]] = col

    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """ 


    ###################################### This is a mock logic. This is not the real validation code. This is for test only 
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
               resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]

    requiresVariantCallerPlugin = False
    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
           uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets
        if  rowStr not in rowErrors:
           rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
           rowWarnings[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"] = uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"] = uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"] = uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if uip["Workflow"] !="":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                #uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
                #uip["DNA_RNA_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["DNA_RNA_Workflow"]
                #uip["OCP_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["OCP_Workflow"]

                # another temporary check which is not required if all the parameters of workflow  were  properly handed off from TS 
                if "RelationshipType" not in uip :
                    msg="INTERNAL ERROR:  For selected workflow "+ uip["Workflow"] + ", an internal key  RelationshipType is missing for row " + rowStr
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    continue

                #bring in all the workflow parameter so far available, into the uip hash.
                for k in  currentlyAvaliableWorkflows[uip["Workflow"]] : 
                    uip[k] = currentlyAvaliableWorkflows[uip["Workflow"]][k]
            else:
                uip["ApplicationType"] = "unknown"
                msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time"
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                continue
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""
        if  "cellularityPct" in uip :
            uip["CellularityPct"] = uip["cellularityPct"]
        if  "CellularityPct" not in uip :
            uip["CellularityPct"] = ""
        if  "cancerType" in uip :
            uip["CancerType"] = uip["cancerType"]
        if  "CancerType" not in uip :
            uip["CancerType"] = ""


        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = uip  #later if its a three level then make it into an array of uips
        else:
            duplicateSamplesExists = True
            theOtherUip = uniqueSamples[uip["sample"]]
            theOtherRowStr = theOtherUip["row"]
            theOtherSetid = theOtherUip["setid"]
            theOtherDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in theOtherUip:
                theOtherDNA_RNA_Workflow = theOtherUip["DNA_RNA_Workflow"]
            thisDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in uip:
                thisDNA_RNA_Workflow = uip["DNA_RNA_Workflow"]
            theOtherNucleotideType = ""
            if "NucleotideType" in theOtherUip:
                theOtherNucleotideType = theOtherUip["NucleotideType"]
            thisNucleotideType = ""
            if "NucleotideType" in uip:
                thisNucleotideType = uip["NucleotideType"]
            # if the rows are for DNA_RNA workflow, then dont complain .. just pass it along..
            #debug print  uip["row"] +" == " + theOtherRowStr + " samplename similarity  " + uip["DNA_RNA_Workflow"] + " == "+ theOtherDNA_RNA_Workflow
            if (       ((uip["Workflow"]=="Upload Only")or(uip["Workflow"] == "")) and (thisNucleotideType != theOtherNucleotideType)     ):
                duplicateSamplesExists = False
            if (       (uip["setid"] == theOtherSetid) and (thisDNA_RNA_Workflow == theOtherDNA_RNA_Workflow ) and (thisDNA_RNA_Workflow == "DNA_RNA")      ):
                duplicateSamplesExists = False
            if duplicateSamplesExists :
                msg ="sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+theOtherRowStr+". Please change the sample name"
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            # else dont flag an error

        # if workflow is empty then dont validate and dont include this row in setid for further validations.
        if uip["Workflow"] =="":
            continue

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            continue
        # save the workflow information of the record on the setID.. also check workflow mismatch with previous row of the same setid
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[]
            setidHash[setid]["firstRecordRow"]=uip["row"]
            setidHash[setid]["firstWorkflow"]=uip["Workflow"]
            setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
            setidHash[setid]["firstRecordDNA_RNA"]=uip["DNA_RNA_Workflow"]
        else:
            previousRow = setidHash[setid]["firstRecordRow"]
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            expectedRelationshipType = setidHash[setid]["firstRelationshipType"]
            #print  uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
            if expectedWorkflow != uip["Workflow"]:
                msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            elif expectedRelationshipType != uip["RelationshipType"]:
                #print  "error on " + uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
                msg="INTERNAL ERROR:  RelationshipType "+ uip["RelationshipType"] + " of the selected workflow, does not match a previous sample with the same SetID, with RelationshipType "+ expectedRelationshipType +" in row "+ previousRow+ "."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
        setidHash[setid]["records"].append(uip)

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"] = uip["sample"]
        if uip["sample"] not in uniqueSamples:    # no need to repeat if the check has been done for the same sample name on an earlier row.
            sampleExistsCallResults = sampleExistsOnIR(inputJson)
            if sampleExistsCallResults.get("error") != "":
                if sampleExistsCallResults.get("status") == "true":
                    msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)

        # check all the generic rules for this uip .. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_4_2(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings)

        row = row + 1


    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the given set of records of the set
        rowsLooked = ""
        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
            # check if any extra roles exists.  Given that the above test exists for lack of roles, it is sufficient if we 
            # verify the total number of roles expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of roles required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            numRecordsForThisSetId = len(setidHash[setid]["records"])
            if (numRecordsForThisSetId > sizeOfRequiredRoles):
                complainAboutTooManyRoles = True

                if setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA":
                    complainAboutTooManyRoles = False

                if complainAboutTooManyRoles:
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of RelationRoles is found. Expected number of roles is " + str(sizeOfRequiredRoles) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)

        ##
        # validate the nucleotidetypes, similar to the roles.
        # first check all the required nucleotides are there in the given set of records of the set
        #    Use the value of the rowsLooked,  populated from the above loop.
        if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")   ): 
            for validNucloetide in setidHash[setid]["validNucleotideTypes"]:
                foundNucleotide=0
                for record in setidHash[setid]["records"]:
                    if validNucloetide == record["NucleotideType"]:   #or NucleotideType
                        foundNucleotide = 1
                if foundNucleotide == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required NucleotideType "+ validNucloetide + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
            # check if any extra nucleotides exists.  Given that the above test exists for missing nucleotides, it is sufficient if we 
            # verify the total number of nucleotides expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of nucleotides required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredNucleotides = len(setidHash[setid]["validNucleotideTypes"])
            #numRecordsForThisSetId = len(setidHash[setid]["records"])   #already done as part of roles check
            if (numRecordsForThisSetId > sizeOfRequiredNucleotides):
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of Nucleotides is found. Expected number of Nucleotides is " + str(sizeOfRequiredNucleotides) + ". "
                if   rowsLooked != "" :
                    if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                    else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)


        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."





    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
           for e in  rowErrors[rowstr]:
              foundAtLeastOneError =1
              emsg = emsg + e + " ; "
        if rowstr in rowWarnings:
           for w in  rowWarnings[rowstr]:
              wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        validationResults.append(k)

    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin


    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
            "conditions": conditions
           }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """

def validateAllRulesOnRecord_4_2(rules, uip, setidHash, rowErrors, rowWarnings):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                #msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                #inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                continue
            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]
                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    if uip[kFor] == vFor :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
                        # another small hardcoded update into the setidHash for later evaluation of the nucleotideType  uniqueness
                        if kValid == "NucleotideType":
                            if setid  in setidHash:
                                if "validNucleotideTypes" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validNucleotideTypes"] = vValid   # this is actually list of valid nucleotideTypes
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]
                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if uip[kFor] == vFor :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
            elif "NonEmpty" in rule:
                kFor=rule["For"]["Name"]
                vFor=rule["For"]["Value"]
                kNonEmpty=rule["NonEmpty"]["Name"]
                #print  "non empty validating   kfor " +kFor  + " vFor "+ vFor + "  kNonEmpty "+ kNonEmpty
                #if kFor not in uip :
                #    print  "kFor not in uip   "  + " kFor "+ kFor 
                #    continue
                if uip[kFor] == vFor :
                    if (   (kNonEmpty not in uip)   or  (uip[kNonEmpty] == "")   ):
                        msg="Empty value found for " + kNonEmpty + " When "+ kFor + " is \"" + vFor +"\"."
                        inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            elif "Disabled" in rule:
                pass
            else:
                 msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                 inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)







def validateUserInput_4_4(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"
    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []
    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
       currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
       orderedColumns[col["Order"]] = col

    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """ 


    ###################################### This is a mock logic. This is not the real validation code. This is for test only 
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
               resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]

    requiresVariantCallerPlugin = False
    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
           uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets
        if  rowStr not in rowErrors:
           rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
           rowWarnings[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"] = uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"] = uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"] = uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if uip["Workflow"] !="":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                #uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
                #uip["DNA_RNA_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["DNA_RNA_Workflow"]
                #uip["OCP_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["OCP_Workflow"]

                # another temporary check which is not required if all the parameters of workflow  were  properly handed off from TS 
                if "RelationshipType" not in uip :
                    msg="INTERNAL ERROR:  For selected workflow "+ uip["Workflow"] + ", an internal key  RelationshipType is missing for row " + rowStr
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    continue

                #bring in all the workflow parameter so far available, into the uip hash.
                for k in  currentlyAvaliableWorkflows[uip["Workflow"]] : 
                    uip[k] = currentlyAvaliableWorkflows[uip["Workflow"]][k]
            else:
                uip["ApplicationType"] = "unknown"
                msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time"
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                continue
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""
        if  "cellularityPct" in uip :
            uip["CellularityPct"] = uip["cellularityPct"]
        if  "CellularityPct" not in uip :
            uip["CellularityPct"] = ""
        if  "cancerType" in uip :
            uip["CancerType"] = uip["cancerType"]
        if  "CancerType" not in uip :
            uip["CancerType"] = ""


        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = uip  #later if its a three level then make it into an array of uips
        else:
            duplicateSamplesExists = True
            theOtherUip = uniqueSamples[uip["sample"]]
            theOtherRowStr = theOtherUip["row"]
            theOtherSetid = theOtherUip["setid"]
            theOtherDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in theOtherUip:
                theOtherDNA_RNA_Workflow = theOtherUip["DNA_RNA_Workflow"]
            thisDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in uip:
                thisDNA_RNA_Workflow = uip["DNA_RNA_Workflow"]
            theOtherNucleotideType = ""
            if "NucleotideType" in theOtherUip:
                theOtherNucleotideType = theOtherUip["NucleotideType"]
            thisNucleotideType = ""
            if "NucleotideType" in uip:
                thisNucleotideType = uip["NucleotideType"]
            # if the rows are for DNA_RNA workflow, then dont complain .. just pass it along..
            #debug print  uip["row"] +" == " + theOtherRowStr + " samplename similarity  " + uip["DNA_RNA_Workflow"] + " == "+ theOtherDNA_RNA_Workflow
            if (       ((uip["Workflow"]=="Upload Only")or(uip["Workflow"] == "")) and (thisNucleotideType != theOtherNucleotideType)     ):
                duplicateSamplesExists = False
            if (       (uip["setid"] == theOtherSetid) and (thisDNA_RNA_Workflow == theOtherDNA_RNA_Workflow ) and (thisDNA_RNA_Workflow == "DNA_RNA")      ):
                duplicateSamplesExists = False
            if duplicateSamplesExists :
                msg ="sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+theOtherRowStr+". Please change the sample name"
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            # else dont flag an error

        # if workflow is empty then dont validate and dont include this row in setid for further validations.
        if uip["Workflow"] =="":
            continue

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            continue
        # save the workflow information of the record on the setID.. also check workflow mismatch with previous row of the same setid
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[]
            setidHash[setid]["firstRecordRow"]=uip["row"]
            setidHash[setid]["firstWorkflow"]=uip["Workflow"]
            setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
            setidHash[setid]["firstRecordDNA_RNA"]=uip["DNA_RNA_Workflow"]
        else:
            previousRow = setidHash[setid]["firstRecordRow"]
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            expectedRelationshipType = setidHash[setid]["firstRelationshipType"]
            #print  uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
            if expectedWorkflow != uip["Workflow"]:
                msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            elif expectedRelationshipType != uip["RelationshipType"]:
                #print  "error on " + uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
                msg="INTERNAL ERROR:  RelationshipType "+ uip["RelationshipType"] + " of the selected workflow, does not match a previous sample with the same SetID, with RelationshipType "+ expectedRelationshipType +" in row "+ previousRow+ "."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
        setidHash[setid]["records"].append(uip)

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"] = uip["sample"]
        if uip["sample"] not in uniqueSamples:    # no need to repeat if the check has been done for the same sample name on an earlier row.
            sampleExistsCallResults = sampleExistsOnIR(inputJson)
            if sampleExistsCallResults.get("error") != "":
                if sampleExistsCallResults.get("status") == "true":
                    msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)

        # check all the generic rules for this uip .. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_4_4(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings)

        row = row + 1


    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the given set of records of the set
        rowsLooked = ""
        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
            # check if any extra roles exists.  Given that the above test exists for lack of roles, it is sufficient if we 
            # verify the total number of roles expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of roles required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            numRecordsForThisSetId = len(setidHash[setid]["records"])
            if (numRecordsForThisSetId > sizeOfRequiredRoles):
                complainAboutTooManyRoles = True

                if setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA":
                    complainAboutTooManyRoles = False

                if complainAboutTooManyRoles:
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of RelationRoles is found. Expected number of roles is " + str(sizeOfRequiredRoles) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)

        ##
        # validate the nucleotidetypes, similar to the roles.
        # first check all the required nucleotides are there in the given set of records of the set
        #    Use the value of the rowsLooked,  populated from the above loop.
        if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")   ): 
            for validNucloetide in setidHash[setid]["validNucleotideTypes"]:
                foundNucleotide=0
                for record in setidHash[setid]["records"]:
                    if validNucloetide == record["NucleotideType"]:   #or NucleotideType
                        foundNucleotide = 1
                if foundNucleotide == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required NucleotideType "+ validNucloetide + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
            # check if any extra nucleotides exists.  Given that the above test exists for missing nucleotides, it is sufficient if we 
            # verify the total number of nucleotides expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of nucleotides required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredNucleotides = len(setidHash[setid]["validNucleotideTypes"])
            #numRecordsForThisSetId = len(setidHash[setid]["records"])   #already done as part of roles check
            if (numRecordsForThisSetId > sizeOfRequiredNucleotides):
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of Nucleotides is found. Expected number of Nucleotides is " + str(sizeOfRequiredNucleotides) + ". "
                if   rowsLooked != "" :
                    if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                    else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)


        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."





    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
           for e in  rowErrors[rowstr]:
              foundAtLeastOneError =1
              emsg = emsg + e + " ; "
        if rowstr in rowWarnings:
           for w in  rowWarnings[rowstr]:
              wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        validationResults.append(k)

    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin

    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
            "conditions": conditions
           }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """

def validateAllRulesOnRecord_4_4(rules, uip, setidHash, rowErrors, rowWarnings):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                #msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                #inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                continue
            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]
                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    if uip[kFor] == vFor :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
                        # another small hardcoded update into the setidHash for later evaluation of the nucleotideType  uniqueness
                        if kValid == "NucleotideType":
                            if setid  in setidHash:
                                if "validNucleotideTypes" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validNucleotideTypes"] = vValid   # this is actually list of valid nucleotideTypes
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]
                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if uip[kFor] == vFor :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
            elif "NonEmpty" in rule:
                kFor=rule["For"]["Name"]
                vFor=rule["For"]["Value"]
                kNonEmpty=rule["NonEmpty"]["Name"]
                #print  "non empty validating   kfor " +kFor  + " vFor "+ vFor + "  kNonEmpty "+ kNonEmpty
                #if kFor not in uip :
                #    print  "kFor not in uip   "  + " kFor "+ kFor 
                #    continue
                if uip[kFor] == vFor :
                    if (   (kNonEmpty not in uip)   or  (uip[kNonEmpty] == "")   ):
                        msg="Empty value found for " + kNonEmpty + " When "+ kFor + " is \"" + vFor +"\"."
                        inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            elif "Disabled" in rule:
                pass
            else:
                 msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                 inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)


def validateUserInput_4_6(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"

    #variantCaller check variables
    requiresVariantCallerPlugin = False
    isVariantCallerSelected = "Unknown"
    if "isVariantCallerSelected" in userInput:
        isVariantCallerSelected = userInput["isVariantCallerSelected"]
    isVariantCallerConfigured = "Unknown"
    if "isVariantCallerConfigured" in userInput:
        isVariantCallerConfigured = userInput["isVariantCallerConfigured"]

    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []
    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
       currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
       orderedColumns[col["Order"]] = col

    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """ 


    ###################################### This is a mock logic. This is not the real validation code. This is for test only 
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
               resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]

    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
           uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets
        if  rowStr not in rowErrors:
           rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
           rowWarnings[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"] = uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"] = uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"] = uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if uip["Workflow"] !="":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                #uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
                #uip["DNA_RNA_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["DNA_RNA_Workflow"]
                #uip["OCP_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["OCP_Workflow"]

                # another temporary check which is not required if all the parameters of workflow  were  properly handed off from TS 
                if "RelationshipType" not in uip :
                    msg="INTERNAL ERROR:  For selected workflow "+ uip["Workflow"] + ", an internal key  RelationshipType is missing for row " + rowStr
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    continue

                #bring in all the workflow parameter so far available, into the uip hash.
                for k in  currentlyAvaliableWorkflows[uip["Workflow"]] : 
                    uip[k] = currentlyAvaliableWorkflows[uip["Workflow"]][k]
            else:
                uip["ApplicationType"] = "unknown"
                msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time"
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                continue
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""
        if  "cellularityPct" in uip :
            uip["CellularityPct"] = uip["cellularityPct"]
        if  "CellularityPct" not in uip :
            uip["CellularityPct"] = ""
        if  "cancerType" in uip :
            uip["CancerType"] = uip["cancerType"]
        if  "CancerType" not in uip :
            uip["CancerType"] = ""


        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = uip  #later if its a three level then make it into an array of uips
        else:
            duplicateSamplesExists = True
            theOtherUip = uniqueSamples[uip["sample"]]
            theOtherRowStr = theOtherUip["row"]
            theOtherSetid = theOtherUip["setid"]
            theOtherDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in theOtherUip:
                theOtherDNA_RNA_Workflow = theOtherUip["DNA_RNA_Workflow"]
            thisDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in uip:
                thisDNA_RNA_Workflow = uip["DNA_RNA_Workflow"]
            theOtherNucleotideType = ""
            if "NucleotideType" in theOtherUip:
                theOtherNucleotideType = theOtherUip["NucleotideType"]
            thisNucleotideType = ""
            if "NucleotideType" in uip:
                thisNucleotideType = uip["NucleotideType"]
            # if the rows are for DNA_RNA workflow, then dont complain .. just pass it along..
            #debug print  uip["row"] +" == " + theOtherRowStr + " samplename similarity  " + uip["DNA_RNA_Workflow"] + " == "+ theOtherDNA_RNA_Workflow
            if (       ((uip["Workflow"]=="Upload Only")or(uip["Workflow"] == "")) and (thisNucleotideType != theOtherNucleotideType)     ):
                duplicateSamplesExists = False
            if (       (uip["setid"] == theOtherSetid) and (thisDNA_RNA_Workflow == theOtherDNA_RNA_Workflow ) and (thisDNA_RNA_Workflow == "DNA_RNA")      ):
                duplicateSamplesExists = False
            if duplicateSamplesExists :
                msg ="sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+theOtherRowStr+". Please change the sample name"
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            # else dont flag an error

        # if workflow is empty then dont validate and dont include this row in setid for further validations.
        if uip["Workflow"] =="":
            continue

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True
            if (  (isVariantCallerSelected != "Unknown")  and (isVariantCallerConfigured != "Unknown")  ):
                if (isVariantCallerSelected != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. Please select and configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    continue
                if (isVariantCallerConfigured != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. The Variant Caller plugin is selected, but not configured. Please configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    continue


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            continue
        # save the workflow information of the record on the setID.. also check workflow mismatch with previous row of the same setid
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[]
            setidHash[setid]["firstRecordRow"]=uip["row"]
            setidHash[setid]["firstWorkflow"]=uip["Workflow"]
            setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
            setidHash[setid]["firstRecordDNA_RNA"]=uip["DNA_RNA_Workflow"]
        else:
            previousRow = setidHash[setid]["firstRecordRow"]
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            expectedRelationshipType = setidHash[setid]["firstRelationshipType"]
            #print  uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
            if expectedWorkflow != uip["Workflow"]:
                msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            elif expectedRelationshipType != uip["RelationshipType"]:
                #print  "error on " + uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
                msg="INTERNAL ERROR:  RelationshipType "+ uip["RelationshipType"] + " of the selected workflow, does not match a previous sample with the same SetID, with RelationshipType "+ expectedRelationshipType +" in row "+ previousRow+ "."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
        setidHash[setid]["records"].append(uip)

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"] = uip["sample"]
        if uip["sample"] not in uniqueSamples:    # no need to repeat if the check has been done for the same sample name on an earlier row.
            sampleExistsCallResults = sampleExistsOnIR(inputJson)
            if sampleExistsCallResults.get("error") != "":
                if sampleExistsCallResults.get("status") == "true":
                    msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)

        # check all the generic rules for this uip .. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_4_6(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings)

        row = row + 1


    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the given set of records of the set
        rowsLooked = ""
        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
            # check if any extra roles exists.  Given that the above test exists for lack of roles, it is sufficient if we 
            # verify the total number of roles expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of roles required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            numRecordsForThisSetId = len(setidHash[setid]["records"])
            if (numRecordsForThisSetId > sizeOfRequiredRoles):
                complainAboutTooManyRoles = True

                if setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA":
                    complainAboutTooManyRoles = False

                if complainAboutTooManyRoles:
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of RelationRoles is found. Expected number of roles is " + str(sizeOfRequiredRoles) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)

        ##
        # validate the nucleotidetypes, similar to the roles.
        # first check all the required nucleotides are there in the given set of records of the set
        #    Use the value of the rowsLooked,  populated from the above loop.
        if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")   ): 
            for validNucloetide in setidHash[setid]["validNucleotideTypes"]:
                foundNucleotide=0
                for record in setidHash[setid]["records"]:
                    if validNucloetide == record["NucleotideType"]:   #or NucleotideType
                        foundNucleotide = 1
                if foundNucleotide == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required NucleotideType "+ validNucloetide + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
            # check if any extra nucleotides exists.  Given that the above test exists for missing nucleotides, it is sufficient if we 
            # verify the total number of nucleotides expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of nucleotides required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredNucleotides = len(setidHash[setid]["validNucleotideTypes"])
            #numRecordsForThisSetId = len(setidHash[setid]["records"])   #already done as part of roles check
            if (numRecordsForThisSetId > sizeOfRequiredNucleotides):
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of Nucleotides is found. Expected number of Nucleotides is " + str(sizeOfRequiredNucleotides) + ". "
                if   rowsLooked != "" :
                    if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                    else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)


        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."





    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
           for e in  rowErrors[rowstr]:
              foundAtLeastOneError =1
              emsg = emsg + e + " ; "
        if rowstr in rowWarnings:
           for w in  rowWarnings[rowstr]:
              wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        validationResults.append(k)

    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin


    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
           "conditions": conditions
           }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """

def validateAllRulesOnRecord_4_6(rules, uip, setidHash, rowErrors, rowWarnings):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                #msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                #inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                continue
            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]
                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    if uip[kFor] == vFor :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
                        # another small hardcoded update into the setidHash for later evaluation of the nucleotideType  uniqueness
                        if kValid == "NucleotideType":
                            if setid  in setidHash:
                                if "validNucleotideTypes" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validNucleotideTypes"] = vValid   # this is actually list of valid nucleotideTypes
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]
                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if uip[kFor] == vFor :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
            elif "NonEmpty" in rule:
                kFor=rule["For"]["Name"]
                vFor=rule["For"]["Value"]
                kNonEmpty=rule["NonEmpty"]["Name"]
                #print  "non empty validating   kfor " +kFor  + " vFor "+ vFor + "  kNonEmpty "+ kNonEmpty
                #if kFor not in uip :
                #    print  "kFor not in uip   "  + " kFor "+ kFor 
                #    continue
                if uip[kFor] == vFor :
                    if (   (kNonEmpty not in uip)   or  (uip[kNonEmpty] == "")   ):
                        msg="Empty value found for " + kNonEmpty + " When "+ kFor + " is \"" + vFor +"\"."
                        inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            elif "Disabled" in rule:
                pass
            else:
                 msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                 inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)




def validateUserInput_5_0(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"

    #variantCaller check variables
    requiresVariantCallerPlugin = False
    isVariantCallerSelected = "Unknown"
    if "isVariantCallerSelected" in userInput:
        isVariantCallerSelected = userInput["isVariantCallerSelected"]
    isVariantCallerConfigured = "Unknown"
    if "isVariantCallerConfigured" in userInput:
        isVariantCallerConfigured = userInput["isVariantCallerConfigured"]

    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    authCheckResult = authCheck(inputJson) 
    #if authCheckResult.get("status") == "false":
    if (   (authCheckResult["status"] !="true")  or (authCheckResult["error"] != "none")   ):
        return {"status": "true",
                "error": "Authentication Failure",
                "validationResults": []}

    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []
    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
       currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
       orderedColumns[col["Order"]] = col

    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """ 


    ###################################### This is a mock logic. This is not the real validation code. This is for test only 
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
               resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]

    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
           uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets
        if  rowStr not in rowErrors:
           rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
           rowWarnings[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"] = uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"] = uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"] = uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if uip["Workflow"] !="":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                #uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
                #uip["DNA_RNA_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["DNA_RNA_Workflow"]
                #uip["OCP_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["OCP_Workflow"]

                # another temporary check which is not required if all the parameters of workflow  were  properly handed off from TS 
                if "RelationshipType" not in uip :
                    msg="INTERNAL ERROR:  For selected workflow "+ uip["Workflow"] + ", an internal key  RelationshipType is missing for row " + rowStr
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    continue

                #bring in all the workflow parameter so far available, into the uip hash.
                for k in  currentlyAvaliableWorkflows[uip["Workflow"]] : 
                    uip[k] = currentlyAvaliableWorkflows[uip["Workflow"]][k]
            else:
                uip["ApplicationType"] = "unknown"
                msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time"
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                continue
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""
        if  "cellularityPct" in uip :
            uip["CellularityPct"] = uip["cellularityPct"]
        if  "CellularityPct" not in uip :
            uip["CellularityPct"] = ""
        if  "cancerType" in uip :
            uip["CancerType"] = uip["cancerType"]
        if  "CancerType" not in uip :
            uip["CancerType"] = ""


        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = uip  #later if its a three level then make it into an array of uips
        else:
            duplicateSamplesExists = True
            theOtherUip = uniqueSamples[uip["sample"]]
            theOtherRowStr = theOtherUip["row"]
            theOtherSetid = theOtherUip["setid"]
            theOtherDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in theOtherUip:
                theOtherDNA_RNA_Workflow = theOtherUip["DNA_RNA_Workflow"]
            thisDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in uip:
                thisDNA_RNA_Workflow = uip["DNA_RNA_Workflow"]
            theOtherNucleotideType = ""
            if "NucleotideType" in theOtherUip:
                theOtherNucleotideType = theOtherUip["NucleotideType"]
            thisNucleotideType = ""
            if "NucleotideType" in uip:
                thisNucleotideType = uip["NucleotideType"]
            # if the rows are for DNA_RNA workflow, then dont complain .. just pass it along..
            #debug print  uip["row"] +" == " + theOtherRowStr + " samplename similarity  " + uip["DNA_RNA_Workflow"] + " == "+ theOtherDNA_RNA_Workflow
            if (       ((uip["Workflow"]=="Upload Only")or(uip["Workflow"] == "")) and (thisNucleotideType != theOtherNucleotideType)     ):
                duplicateSamplesExists = False
            if (       (uip["setid"] == theOtherSetid) and (thisDNA_RNA_Workflow == theOtherDNA_RNA_Workflow ) and (thisDNA_RNA_Workflow == "DNA_RNA")      ):
                duplicateSamplesExists = False
            if duplicateSamplesExists :
                msg ="sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+theOtherRowStr+". Please change the sample name"
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            # else dont flag an error

        # if workflow is empty then dont validate and dont include this row in setid for further validations.
        if uip["Workflow"] =="":
            continue

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True
            if (  (isVariantCallerSelected != "Unknown")  and (isVariantCallerConfigured != "Unknown")  ):
                if (isVariantCallerSelected != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. Please select and configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    continue
                if (isVariantCallerConfigured != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. The Variant Caller plugin is selected, but not configured. Please configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    continue


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            continue
        # save the workflow information of the record on the setID.. also check workflow mismatch with previous row of the same setid
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[]
            setidHash[setid]["firstRecordRow"]=uip["row"]
            setidHash[setid]["firstWorkflow"]=uip["Workflow"]
            setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
            setidHash[setid]["firstRecordDNA_RNA"]=uip["DNA_RNA_Workflow"]
        else:
            previousRow = setidHash[setid]["firstRecordRow"]
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            expectedRelationshipType = setidHash[setid]["firstRelationshipType"]
            #print  uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
            if expectedWorkflow != uip["Workflow"]:
                msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            elif expectedRelationshipType != uip["RelationshipType"]:
                #print  "error on " + uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
                msg="INTERNAL ERROR:  RelationshipType "+ uip["RelationshipType"] + " of the selected workflow, does not match a previous sample with the same SetID, with RelationshipType "+ expectedRelationshipType +" in row "+ previousRow+ "."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
        setidHash[setid]["records"].append(uip)

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"] = uip["sample"]
        if uip["sample"] not in uniqueSamples:    # no need to repeat if the check has been done for the same sample name on an earlier row.
            sampleExistsCallResults = sampleExistsOnIR(inputJson)
            if sampleExistsCallResults.get("error") != "":
                if sampleExistsCallResults.get("status") == "true":
                    msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)

        # check all the generic rules for this uip .. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_5_0(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings)

        row = row + 1


    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the given set of records of the set
        rowsLooked = ""
        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
            # check if any extra roles exists.  Given that the above test exists for lack of roles, it is sufficient if we 
            # verify the total number of roles expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of roles required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            numRecordsForThisSetId = len(setidHash[setid]["records"])
            if (numRecordsForThisSetId > sizeOfRequiredRoles):
                complainAboutTooManyRoles = True

                if setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA":
                    complainAboutTooManyRoles = False

                if complainAboutTooManyRoles:
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of RelationRoles is found. Expected number of roles is " + str(sizeOfRequiredRoles) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)

        ##
        # validate the nucleotidetypes, similar to the roles.
        # first check all the required nucleotides are there in the given set of records of the set
        #    Use the value of the rowsLooked,  populated from the above loop.
        if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")   ): 
            for validNucloetide in setidHash[setid]["validNucleotideTypes"]:
                foundNucleotide=0
                for record in setidHash[setid]["records"]:
                    if validNucloetide == record["NucleotideType"]:   #or NucleotideType
                        foundNucleotide = 1
                if foundNucleotide == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required NucleotideType "+ validNucloetide + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
            # check if any extra nucleotides exists.  Given that the above test exists for missing nucleotides, it is sufficient if we 
            # verify the total number of nucleotides expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of nucleotides required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredNucleotides = len(setidHash[setid]["validNucleotideTypes"])
            #numRecordsForThisSetId = len(setidHash[setid]["records"])   #already done as part of roles check
            if (numRecordsForThisSetId > sizeOfRequiredNucleotides):
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of Nucleotides is found. Expected number of Nucleotides is " + str(sizeOfRequiredNucleotides) + ". "
                if   rowsLooked != "" :
                    if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                    else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)


        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."





    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
           for e in  rowErrors[rowstr]:
              foundAtLeastOneError =1
              emsg = emsg + e + " ; "
        if rowstr in rowWarnings:
           for w in  rowWarnings[rowstr]:
              wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        validationResults.append(k)

    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin


    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
           "conditions": conditions
           }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """

def validateAllRulesOnRecord_5_0(rules, uip, setidHash, rowErrors, rowWarnings):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                #msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                #inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                continue
            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]
                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    if uip[kFor] == vFor :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
                        # another small hardcoded update into the setidHash for later evaluation of the nucleotideType  uniqueness
                        if kValid == "NucleotideType":
                            if setid  in setidHash:
                                if "validNucleotideTypes" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validNucleotideTypes"] = vValid   # this is actually list of valid nucleotideTypes
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]
                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if uip[kFor] == vFor :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
            elif "NonEmpty" in rule:
                kFor=rule["For"]["Name"]
                vFor=rule["For"]["Value"]
                kNonEmpty=rule["NonEmpty"]["Name"]
                #print  "non empty validating   kfor " +kFor  + " vFor "+ vFor + "  kNonEmpty "+ kNonEmpty
                #if kFor not in uip :
                #    print  "kFor not in uip   "  + " kFor "+ kFor 
                #    continue
                if uip[kFor] == vFor :
                    if (   (kNonEmpty not in uip)   or  (uip[kNonEmpty] == "")   ):
                        #msg="Empty value found for " + kNonEmpty + " When "+ kFor + " is \"" + vFor +"\"."
                        msg="Empty value found for " + kNonEmpty
                        inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            elif "Disabled" in rule:
                pass
            else:
                 msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                 inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)



def validateUserInput_5_2(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"

    #variantCaller check variables
    requiresVariantCallerPlugin = False
    isVariantCallerSelected = "Unknown"
    if "isVariantCallerSelected" in userInput:
        isVariantCallerSelected = userInput["isVariantCallerSelected"]
    isVariantCallerConfigured = "Unknown"
    if "isVariantCallerConfigured" in userInput:
        isVariantCallerConfigured = userInput["isVariantCallerConfigured"]

    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    authCheckResult = authCheck(inputJson) 
    #if authCheckResult.get("status") == "false":
    if (   (authCheckResult["status"] !="true")  or (authCheckResult["error"] != "none")   ):
        return {"status": "true",
                "error": "Authentication Failure",
                "validationResults": []}

    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []
    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
       currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
       orderedColumns[col["Order"]] = col

    # Get cancer types
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    # Extracting Gender column from the current rules for validation purpose. 
    validGenderList = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Gender"):
            validGenderList = col["Values"]

    # Extracting Relation column from the current rules for validation purpose.
    validRelations = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Relation"):
            validRelations = col["Values"]

    # getting the complete workflow list to extract the relationship type.
    allWorkflowListResult = getWorkflowList(inputJson)
    if (allWorkflowListResult["status"] != "true"):
        return allWorkflowListResult
    allWorkflowList = allWorkflowListResult["userWorkflows"]
    
    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """


    ###################################### This is a mock logic. This is not the real validation code. This is for test only
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
               resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    rowHighlightableFields={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]

    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
           uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets.  Also do the same for highlightableFields
        if  rowStr not in rowErrors:
           rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
           rowWarnings[rowStr]=[]
        if  rowStr not in rowHighlightableFields:
           rowHighlightableFields[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"] = uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"] = uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"] = uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if uip["Workflow"] !="":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                #uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
                #uip["DNA_RNA_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["DNA_RNA_Workflow"]
                #uip["OCP_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["OCP_Workflow"]
                if "RelationshipType" in currentlyAvaliableWorkflows[uip["Workflow"]]:
                    currentWorkflowDetails = currentlyAvaliableWorkflows[uip["Workflow"]]
                    if uip["RelationshipType"] and (currentWorkflowDetails["RelationshipType"] != uip["RelationshipType"]):
                        msg="selected relation "+ uip["RelationshipType"] + " is not valid." + rowStr
                        inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                        continue
                # another temporary check which is not required if all the parameters of workflow  were  properly handed off from TS
                if "RelationshipType" not in uip :
                    msg="INTERNAL ERROR:  For selected workflow "+ uip["Workflow"] + ", an internal key  RelationshipType is missing for row " + rowStr
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue

                #bring in all the workflow parameter so far available, into the uip hash.
                for k in  currentlyAvaliableWorkflows[uip["Workflow"]] :
                    uip[k] = currentlyAvaliableWorkflows[uip["Workflow"]][k]

                #Override cellularity percentage based on DNA RNA workflows
                if (uip["DNA_RNA_Workflow"] == "DNA_RNA"):
                    if (uip["nucleotideType"] == "DNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "1"
                    elif (uip["nucleotideType"] == "RNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "0"
            else:
                uip["ApplicationType"] = "unknown"
                msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time"
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                continue
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""
        if  "cellularityPct" in uip :
            uip["CellularityPct"] = uip["cellularityPct"]
        if  "CellularityPct" not in uip :
            uip["CellularityPct"] = ""
        if  "cancerType" in uip :
            uip["CancerType"] = uip["cancerType"]
        if  "CancerType" not in uip :
            uip["CancerType"] = ""
                
        if(uip["CancerType"] and (uip["CancerType"] not in cancerTypesList)):
            msg="selected cancer type "+ uip["CancerType"] + " is not valid for this IR user account. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["Gender"] and (uip["Gender"] not in validGenderList)):
            msg="selected gender type "+ uip["Gender"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["RelationRole"] and (uip["RelationRole"] not in validRelations)):
            msg="selected relation role "+ uip["RelationRole"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            continue

        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = uip  #later if its a three level then make it into an array of uips
        else:
            duplicateSamplesExists = True
            theOtherUip = uniqueSamples[uip["sample"]]
            theOtherRowStr = theOtherUip["row"]
            theOtherSetid = theOtherUip["setid"]
            theOtherDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in theOtherUip:
                theOtherDNA_RNA_Workflow = theOtherUip["DNA_RNA_Workflow"]
            thisDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in uip:
                thisDNA_RNA_Workflow = uip["DNA_RNA_Workflow"]
            theOtherNucleotideType = ""
            if "NucleotideType" in theOtherUip:
                theOtherNucleotideType = theOtherUip["NucleotideType"]
            thisNucleotideType = ""
            if "NucleotideType" in uip:
                thisNucleotideType = uip["NucleotideType"]
            # if the rows are for DNA_RNA workflow, then dont complain .. just pass it along..
            #debug print  uip["row"] +" == " + theOtherRowStr + " samplename similarity  " + uip["DNA_RNA_Workflow"] + " == "+ theOtherDNA_RNA_Workflow
            if (       ((uip["Workflow"]=="Upload Only")or(uip["Workflow"] == "")) and (thisNucleotideType != theOtherNucleotideType)     ):
                duplicateSamplesExists = False
            if (       (uip["setid"] == theOtherSetid) and (thisDNA_RNA_Workflow == theOtherDNA_RNA_Workflow ) and (thisDNA_RNA_Workflow == "DNA_RNA")      ):
                duplicateSamplesExists = False
            if duplicateSamplesExists :
                msg ="sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+theOtherRowStr+". Please change the sample name"
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
            # else dont flag an error

        # if workflow is empty then dont validate and dont include this row in setid for further validations.
        if uip["Workflow"] =="":
            continue

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True
            if (  (isVariantCallerSelected != "Unknown")  and (isVariantCallerConfigured != "Unknown")  ):
                if (isVariantCallerSelected != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. Please select and configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue
                if (isVariantCallerConfigured != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. The Variant Caller plugin is selected, but not configured. Please configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
            continue
        # save the workflow information of the record on the setID.. also check workflow mismatch with previous row of the same setid
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[]
            setidHash[setid]["firstRecordRow"]=uip["row"]
            setidHash[setid]["firstApplicationType"]=uip["ApplicationType"]
            setidHash[setid]["firstWorkflow"]=uip["Workflow"]
            setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
            if "AllowMultipleRoleRecords" in uip : 
                setidHash[setid]["firstAllowMultipleRoleRecords"]=uip["AllowMultipleRoleRecords"]
            setidHash[setid]["firstRecordDNA_RNA"]=uip["DNA_RNA_Workflow"]
        else:
            previousRow = setidHash[setid]["firstRecordRow"]
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            expectedRelationshipType = setidHash[setid]["firstRelationshipType"]
            expectedApplicationType = setidHash[setid]["firstApplicationType"]
            #print  uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
            if expectedWorkflow != uip["Workflow"]:
                msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
            elif expectedRelationshipType != uip["RelationshipType"]:
                #print  "error on " + uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
                msg="INTERNAL ERROR:  RelationshipType "+ uip["RelationshipType"] + " of the selected workflow, does not match a previous sample with the same SetID, with RelationshipType "+ expectedRelationshipType +" in row "+ previousRow+ "."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #elif expectedApplicationType != uip["ApplicationType"]:  #TBD add similar internal error
        setidHash[setid]["records"].append(uip)

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"] = uip["sample"]
        if uip["sample"] not in uniqueSamples:    # no need to repeat if the check has been done for the same sample name on an earlier row.
            sampleExistsCallResults = sampleExistsOnIR(inputJson)
            if sampleExistsCallResults.get("error") != "":
                if sampleExistsCallResults.get("status") == "true":
                    msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)

        # check all the generic rules for this uip .. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_5_2(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields)

        row = row + 1


    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the given set of records of the set
        rowsLooked = ""
        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)
            # check if any extra roles exists.  Given that the above test exists for lack of roles, it is sufficient if we 
            # verify the total number of roles expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of roles required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            numRecordsForThisSetId = len(setidHash[setid]["records"])
            if (numRecordsForThisSetId > sizeOfRequiredRoles):
                complainAboutTooManyRoles = True

                # ignore this check if the application type or other workflow settings already allws multi roles
                if "firstAllowMultipleRoleRecords" in setidHash[setid]:
                    if setidHash[setid]["firstAllowMultipleRoleRecords"] == "true":
                        complainAboutTooManyRoles = False
                # for DNA_RNA flag, its not the roles to be evaluated, its the nucleotideTypes to be evaluated.
                if setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA":
                    complainAboutTooManyRoles = False

                if complainAboutTooManyRoles:
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of RelationRoles is found. Expected number of roles is " + str(sizeOfRequiredRoles) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)

        ##
        # validate the nucleotidetypes, similar to the roles.
        # first check all the required nucleotides are there in the given set of records of the set
        #    Use the value of the rowsLooked,  populated from the above loop.
        if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")   ): 
            for validNucloetide in setidHash[setid]["validNucleotideTypes"]:
                foundNucleotide=0
                for record in setidHash[setid]["records"]:
                    if validNucloetide == record["NucleotideType"]:   #or NucleotideType
                        foundNucleotide = 1
                if foundNucleotide == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required NucleotideType "+ validNucloetide + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)
            # check if any extra nucleotides exists.  Given that the above test exists for missing nucleotides, it is sufficient if we 
            # verify the total number of nucleotides expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of nucleotides required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredNucleotides = len(setidHash[setid]["validNucleotideTypes"])
            #numRecordsForThisSetId = len(setidHash[setid]["records"])   #already done as part of roles check
            if (numRecordsForThisSetId > sizeOfRequiredNucleotides):
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of Nucleotides is found. Expected number of Nucleotides is " + str(sizeOfRequiredNucleotides) + ". "
                if   rowsLooked != "" :
                    if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                    else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)


        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."





    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
           for e in  rowErrors[rowstr]:
              foundAtLeastOneError =1
              emsg = emsg + e + " ; "
        if rowstr in rowWarnings:
           for w in  rowWarnings[rowstr]:
              wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        if rowstr in rowHighlightableFields:
           k["highlightableFields"]=rowHighlightableFields[rowstr]
        else:
           k["highlightableFields"]=[]
        validationResults.append(k)

    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin


    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
           "conditions": conditions
           }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """


def validateAllRulesOnRecord_5_2(rules, uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                #msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                #inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                continue

            andForExists = 0
            if "AndFor" in rule:
                if rule["AndFor"]["Name"] not in uip:
                    continue
                else:
                    andForExists = 1

            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1
                    if valueCheck == 1 :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kValid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
                        # another small hardcoded update into the setidHash for later evaluation of the nucleotideType  uniqueness
                        if kValid == "NucleotideType":
                            if setid  in setidHash:
                                if "validNucleotideTypes" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validNucleotideTypes"] = vValid   # this is actually list of valid nucleotideTypes
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if valueCheck == 1 :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kInvalid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "NonEmpty" in rule:
                kFor=rule["For"]["Name"]
                vFor=rule["For"]["Value"]
                kNonEmpty=rule["NonEmpty"]["Name"]
                #print  "non empty validating   kfor " +kFor  + " vFor "+ vFor + "  kNonEmpty "+ kNonEmpty
                #if kFor not in uip :
                #    print  "kFor not in uip   "  + " kFor "+ kFor 
                #    continue
                if uip[kFor] == vFor :
                    if (   (kNonEmpty not in uip)   or  (uip[kNonEmpty] == "")   ):
                        #msg="Empty value found for " + kNonEmpty + " When "+ kFor + " is \"" + vFor +"\"."
                        msg="Empty value found for " + kNonEmpty
                        inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(row, kNonEmpty, rowHighlightableFields)
                        inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "Disabled" in rule:
                pass
            else:
                 msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                 inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)


def validateUserInput_5_4(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"

    #variantCaller check variables
    requiresVariantCallerPlugin = False
    isVariantCallerSelected = "Unknown"
    if "isVariantCallerSelected" in userInput:
        isVariantCallerSelected = userInput["isVariantCallerSelected"]
    isVariantCallerConfigured = "Unknown"
    if "isVariantCallerConfigured" in userInput:
        isVariantCallerConfigured = userInput["isVariantCallerConfigured"]

    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    authCheckResult = authCheck(inputJson) 
    #if authCheckResult.get("status") == "false":
    if (   (authCheckResult["status"] !="true")  or (authCheckResult["error"] != "none")   ):
        return {"status": "true",
                "error": "Authentication Failure",
                "validationResults": []}

    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []

    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
       currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
       orderedColumns[col["Order"]] = col

    # Get cancer types
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    # Extracting Gender column from the current rules for validation purpose. 
    validGenderList = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Gender"):
            validGenderList = col["Values"]

    # Extracting Relation column from the current rules for validation purpose.
    validRelations = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Relation"):
            validRelations = col["Values"]

    # getting the complete workflow list to extract the relationship type.
    allWorkflowListResult = getWorkflowList(inputJson)
    if (allWorkflowListResult["status"] != "true"):
        return allWorkflowListResult
    allWorkflowList = allWorkflowListResult["userWorkflows"]

    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """


    ###################################### This is a mock logic. This is not the real validation code. This is for test only
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
               resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    rowHighlightableFields={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]

    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
           uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets.  Also do the same for highlightableFields
        if  rowStr not in rowErrors:
           rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
           rowWarnings[rowStr]=[]
        if  rowStr not in rowHighlightableFields:
           rowHighlightableFields[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"] = uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"] = uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"] = uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if uip["Workflow"] !="":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                #uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
                #uip["DNA_RNA_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["DNA_RNA_Workflow"]
                #uip["OCP_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["OCP_Workflow"]
                if "RelationshipType" in currentlyAvaliableWorkflows[uip["Workflow"]]:
                    currentWorkflowDetails = currentlyAvaliableWorkflows[uip["Workflow"]]
                    if uip["RelationshipType"] and (currentWorkflowDetails["RelationshipType"] != uip["RelationshipType"]):
                        msg="selected relation "+ uip["RelationshipType"] + " is not valid." + rowStr
                        inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                        continue

                # another temporary check which is not required if all the parameters of workflow  were  properly handed off from TS
                if "RelationshipType" not in uip :
                    msg="INTERNAL ERROR:  For selected workflow "+ uip["Workflow"] + ", an internal key  RelationshipType is missing for row " + rowStr
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue

                #bring in all the workflow parameter so far available, into the uip hash.
                for k in  currentlyAvaliableWorkflows[uip["Workflow"]] :
                    uip[k] = currentlyAvaliableWorkflows[uip["Workflow"]][k]

                #Override cellularity percentage based on DNA RNA workflows
                if (uip["DNA_RNA_Workflow"] == "DNA_RNA"):
                    if (uip["nucleotideType"] == "DNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "1"
                    elif (uip["nucleotideType"] == "RNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "0"
            else:
                uip["ApplicationType"] = "unknown"
                msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time" + rowStr
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                continue
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""
        if  "cellularityPct" in uip :
            uip["CellularityPct"] = uip["cellularityPct"]
        if  "CellularityPct" not in uip :
            uip["CellularityPct"] = ""
        if  "cancerType" in uip :
            uip["CancerType"] = uip["cancerType"]
        if  "CancerType" not in uip :
            uip["CancerType"] = ""
        if  "controlType" in uip :
            if uip["controlType"] == "None":
                uip["ControlType"] = ""
            else:
                uip["ControlType"] = uip["controlType"]
        if  "controlType" not in uip :
            uip["ControlType"] = ""
        if  "reference" in uip :
            uip["Reference"] = uip["reference"]
        if  "reference" not in uip :
            uip["Reference"] = ""
        if  "hotSpotRegionBedFile" in uip :
            uip["HotSpotRegionBedFile"] = uip["hotSpotRegionBedFile"]
        if  "hotSpotRegionBedFile" not in uip :
            uip["HotSpotRegionBedFile"] = ""
        if  "targetRegionBedFile" in uip :
            uip["TargetRegionBedFile"] = uip["targetRegionBedFile"]
        if  "targetRegionBedFile" not in uip :
            uip["TargetRegionBedFile"] = ""
            

        if(uip["CancerType"] and (uip["CancerType"] not in cancerTypesList)):
            msg="selected cancer type "+ uip["CancerType"] + " is not valid for this IR user account. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["Gender"] and (uip["Gender"] not in validGenderList)):
            msg="selected gender type "+ uip["Gender"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["RelationRole"] and (uip["RelationRole"] not in validRelations)):
            msg="selected relation role "+ uip["RelationRole"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            continue

        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = uip  #later if its a three level then make it into an array of uips
        else:
            duplicateSamplesExists = True
            theOtherUip = uniqueSamples[uip["sample"]]
            theOtherRowStr = theOtherUip["row"]
            theOtherSetid = theOtherUip["setid"]
            theOtherRelation = theOtherUip["Relation"]
            theOtherRelationShipType = theOtherUip["RelationshipType"]
            theOtherGender = theOtherUip["Gender"]
            if  "controlType" in theOtherUip :
                if theOtherUip["controlType"] == "None":
                    theOtherUipControlType = ""
                else:
                    theOtherUipControlType = theOtherUip["controlType"]
            if  "controlType" not in theOtherUip :
                theOtherUipControlType = ""
            if  "reference" in theOtherUip :
                theOtherUipReference = theOtherUip["reference"]
            if  "reference" not in theOtherUip :
                theOtherUipReference = ""
            if  "hotSpotRegionBedFile" in theOtherUip :
                theOtherUipHotSpotRegionBedFile = theOtherUip["hotSpotRegionBedFile"]
            if  "hotSpotRegionBedFile" not in theOtherUip :
                theOtherUipHotSpotRegionBedFile = ""
            if  "targetRegionBedFile" in theOtherUip :
                theOtherUipTargetRegionBedFile = theOtherUip["targetRegionBedFile"]
            if  "targetRegionBedFile" not in theOtherUip :
                theOtherUipTargetRegionBedFile = ""

            write_debug_log("OtherSetid: " + theOtherSetid + ", theOtherRelation: " + theOtherRelation + ", theOtherRelationShipType: " + theOtherRelationShipType + ", theOtherGender: " + theOtherGender + ", theOtherControlType: " + theOtherUipControlType + ", theOtherUipReference: " + theOtherUipReference + ", theOtherUipHotSpotRegionBedFile: " + theOtherUipHotSpotRegionBedFile + ", theOtherUipTargetRegionBedFile: " + theOtherUipTargetRegionBedFile)
            write_debug_log("this Setid: " + uip["setid"] + ", Relation: " + uip["Relation"] + ", RelationshipType: " + uip["RelationshipType"] + ", Gender: " + uip["Gender"] + ", ControlType: " + uip["ControlType"] + ", Reference: " + uip["Reference"] + ", HotSpotRegionBedFile: " + uip["HotSpotRegionBedFile"] + ", TargetRegionBedFile: " + uip["TargetRegionBedFile"])

            theOtherDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in theOtherUip:
                theOtherDNA_RNA_Workflow = theOtherUip["DNA_RNA_Workflow"]
            thisDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in uip:
                thisDNA_RNA_Workflow = uip["DNA_RNA_Workflow"]
            theOtherNucleotideType = ""
            if "NucleotideType" in theOtherUip:
                theOtherNucleotideType = theOtherUip["NucleotideType"]
            thisNucleotideType = ""
            if "NucleotideType" in uip:
                thisNucleotideType = uip["NucleotideType"]
            # if the rows are for DNA_RNA workflow, then dont complain .. just pass it along..
            #debug print  uip["row"] +" == " + theOtherRowStr + " samplename similarity  " + uip["DNA_RNA_Workflow"] + " == "+ theOtherDNA_RNA_Workflow
            if (       ((uip["Workflow"]=="Upload Only")or(uip["Workflow"] == "")) and (thisNucleotideType != theOtherNucleotideType)     ):
                duplicateSamplesExists = False
            if (       (uip["setid"] == theOtherSetid) and (thisDNA_RNA_Workflow == theOtherDNA_RNA_Workflow ) and (thisDNA_RNA_Workflow == "DNA_RNA")      ):
                duplicateSamplesExists = False

            fieldValueDiffers = False
            if (uip["setid"] != theOtherSetid):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)      # TDB: Highlighting fields in these below conditions is not working, Check later.
            if (uip["Relation"] != theOtherRelation):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Relation", rowHighlightableFields)
            if (uip["RelationshipType"] != theOtherRelationShipType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
            if (uip["Gender"] != theOtherGender):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Gender", rowHighlightableFields)
            if (uip["ControlType"] != theOtherUipControlType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "ControlType", rowHighlightableFields)
            if (uip["Reference"] != theOtherUipReference):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Reference", rowHighlightableFields)
            if (uip["HotSpotRegionBedFile"] != theOtherUipHotSpotRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "HotSpotRegionBedFile", rowHighlightableFields)
            if (uip["TargetRegionBedFile"] != theOtherUipTargetRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "TargetRegionBedFile", rowHighlightableFields)

            if not fieldValueDiffers:
                duplicateSamplesExists = False


            if duplicateSamplesExists :
                msg ="Sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+theOtherRowStr+", Please change the sample name. Or, If you intend to use multi-barcodes per sample then please make sure all the other field values are same for all corresponding rows."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
                continue
            # else dont flag an error

        # if workflow is empty then dont validate and dont include this row in setid for further validations.
        if uip["Workflow"] =="":
            continue

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True
            if (  (isVariantCallerSelected != "Unknown")  and (isVariantCallerConfigured != "Unknown")  ):
                if (isVariantCallerSelected != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. Please select and configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue
                if (isVariantCallerConfigured != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. The Variant Caller plugin is selected, but not configured. Please configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
            continue
        # save the workflow information of the record on the setID.. also check workflow mismatch with previous row of the same setid
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[]
            setidHash[setid]["firstRecordRow"]=uip["row"]
            setidHash[setid]["firstApplicationType"]=uip["ApplicationType"]
            setidHash[setid]["firstWorkflow"]=uip["Workflow"]
            setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
            if "AllowMultipleRoleRecords" in uip : 
                setidHash[setid]["firstAllowMultipleRoleRecords"]=uip["AllowMultipleRoleRecords"]
            setidHash[setid]["firstRecordDNA_RNA"]=uip["DNA_RNA_Workflow"]
        else:
            previousRow = setidHash[setid]["firstRecordRow"]
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            expectedRelationshipType = setidHash[setid]["firstRelationshipType"]
            expectedApplicationType = setidHash[setid]["firstApplicationType"]
            #print  uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
            if expectedWorkflow != uip["Workflow"]:
                msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
            elif expectedRelationshipType != uip["RelationshipType"]:
                #print  "error on " + uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
                msg="INTERNAL ERROR:  RelationshipType "+ uip["RelationshipType"] + " of the selected workflow, does not match a previous sample with the same SetID, with RelationshipType "+ expectedRelationshipType +" in row "+ previousRow+ "."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #elif expectedApplicationType != uip["ApplicationType"]:  #TBD add similar internal error
        setidHash[setid]["records"].append(uip)

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"] = uip["sample"]
        if uip["sample"] not in uniqueSamples:    # no need to repeat if the check has been done for the same sample name on an earlier row.
            sampleExistsCallResults = sampleExistsOnIR(inputJson)
            if sampleExistsCallResults.get("error") != "":
                if sampleExistsCallResults.get("status") == "true":
                    msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)

        # check all the generic rules for this uip .. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_5_4(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields)

        row = row + 1


    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the given set of records of the set
        rowsLooked = ""
        uniqueSamplesForThisSetID = []
        for record in setidHash[setid]["records"]:
            if record["sample"] not in uniqueSamplesForThisSetID:
                uniqueSamplesForThisSetID.append(record["sample"])
            

        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)
            # check if any extra roles exists.  Given that the above test exists for lack of roles, it is sufficient if we 
            # verify the total number of roles expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of roles required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            numRecordsForThisSetId = len(setidHash[setid]["records"])
            if (numRecordsForThisSetId > sizeOfRequiredRoles):
                complainAboutTooManyRoles = True

                uniqueRoles = []
                for uipInRecords in setidHash[setid]["records"]:
                    if (uipInRecords["Relation"] not in uniqueRoles):
                        uniqueRoles.append(uipInRecords["Relation"])
                if(len(uniqueRoles) == sizeOfRequiredRoles):
                    complainAboutTooManyRoles = False

                # ignore this check if the application type or other workflow settings already allws multi roles
                if "firstAllowMultipleRoleRecords" in setidHash[setid]:
                    if setidHash[setid]["firstAllowMultipleRoleRecords"] == "true":
                        complainAboutTooManyRoles = False
                # for DNA_RNA flag, its not the roles to be evaluated, its the nucleotideTypes to be evaluated.
                if setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA":
                    complainAboutTooManyRoles = False

                if complainAboutTooManyRoles:
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of RelationRoles is found. Expected number of roles is " + str(sizeOfRequiredRoles) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)

        ##
        # validate the nucleotidetypes, similar to the roles.
        # first check all the required nucleotides are there in the given set of records of the set
        #    Use the value of the rowsLooked,  populated from the above loop.
        if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")   ): 
            for validNucloetide in setidHash[setid]["validNucleotideTypes"]:
                foundNucleotide=0
                for record in setidHash[setid]["records"]:
                    if validNucloetide == record["NucleotideType"]:   #or NucleotideType
                        foundNucleotide = 1
                if foundNucleotide == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required NucleotideType "+ validNucloetide + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)
            # check if any extra nucleotides exists.  Given that the above test exists for missing nucleotides, it is sufficient if we 
            # verify the total number of nucleotides expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of nucleotides required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredNucleotides = len(setidHash[setid]["validNucleotideTypes"])
            numberOfUniqueSamples = len(uniqueSamplesForThisSetID)
            #numRecordsForThisSetId = len(setidHash[setid]["records"])   #already done as part of roles check
            if (numberOfUniqueSamples > sizeOfRequiredNucleotides):
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of Nucleotides is found. Expected number of Nucleotides is " + str(sizeOfRequiredNucleotides) + ". "
                if   rowsLooked != "" :
                    if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                    else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)


        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."





    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
           for e in  rowErrors[rowstr]:
              foundAtLeastOneError =1
              emsg = emsg + e + " ; "
        if rowstr in rowWarnings:
           for w in  rowWarnings[rowstr]:
              wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        if rowstr in rowHighlightableFields:
           k["highlightableFields"]=rowHighlightableFields[rowstr]
        else:
           k["highlightableFields"]=[]
        validationResults.append(k)

    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin


    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
           "conditions": conditions
           }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """

def validateAllRulesOnRecord_5_4(rules, uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                #msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                #inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                continue

            andForExists = 0
            if "AndFor" in rule:
                if rule["AndFor"]["Name"] not in uip:
                    continue
                else:
                    andForExists = 1

            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1
                    if valueCheck == 1 :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kValid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
                        # another small hardcoded update into the setidHash for later evaluation of the nucleotideType  uniqueness
                        if kValid == "NucleotideType":
                            if setid  in setidHash:
                                if "validNucleotideTypes" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validNucleotideTypes"] = vValid   # this is actually list of valid nucleotideTypes
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if valueCheck == 1 :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kInvalid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "NonEmpty" in rule:
                kFor=rule["For"]["Name"]
                vFor=rule["For"]["Value"]
                kNonEmpty=rule["NonEmpty"]["Name"]
                #print  "non empty validating   kfor " +kFor  + " vFor "+ vFor + "  kNonEmpty "+ kNonEmpty
                #if kFor not in uip :
                #    print  "kFor not in uip   "  + " kFor "+ kFor 
                #    continue
                if uip[kFor] == vFor :
                    if (   (kNonEmpty not in uip)   or  (uip[kNonEmpty] == "")   ):
                        #msg="Empty value found for " + kNonEmpty + " When "+ kFor + " is \"" + vFor +"\"."
                        msg="Empty value found for " + kNonEmpty
                        inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(row, kNonEmpty, rowHighlightableFields)
                        inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "Disabled" in rule:
                pass
            else:
                 msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                 inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

def validateUserInput_5_6(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"

    #variantCaller check variables
    requiresVariantCallerPlugin = False
    isVariantCallerSelected = "Unknown"
    if "isVariantCallerSelected" in userInput:
        isVariantCallerSelected = userInput["isVariantCallerSelected"]
    isVariantCallerConfigured = "Unknown"
    if "isVariantCallerConfigured" in userInput:
        isVariantCallerConfigured = userInput["isVariantCallerConfigured"]

    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    authCheckResult = authCheck(inputJson) 
    #if authCheckResult.get("status") == "false":
    if (   (authCheckResult["status"] !="true")  or (authCheckResult["error"] != "none")   ):
        return {"status": "true",
                "error": "Authentication Failure",
                "validationResults": []}

    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []

    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
       currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
       orderedColumns[col["Order"]] = col

    # Get cancer types
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    # Extracting Gender column from the current rules for validation purpose. 
    validGenderList = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Gender"):
            validGenderList = col["Values"]

    # Extracting Relation column from the current rules for validation purpose.
    validRelations = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Relation"):
            validRelations = col["Values"]

    # getting the complete workflow list to extract the relationship type.
    allWorkflowListResult = getWorkflowList(inputJson)
    if (allWorkflowListResult["status"] != "true"):
        return allWorkflowListResult
    allWorkflowList = allWorkflowListResult["userWorkflows"]

    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """


    ###################################### This is a mock logic. This is not the real validation code. This is for test only
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
               resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    rowHighlightableFields={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]

    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
           uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets.  Also do the same for highlightableFields
        if  rowStr not in rowErrors:
           rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
           rowWarnings[rowStr]=[]
        if  rowStr not in rowHighlightableFields:
           rowHighlightableFields[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"] = uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"] = uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"] = uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if uip["Workflow"] !="":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                #uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
                #uip["DNA_RNA_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["DNA_RNA_Workflow"]
                #uip["OCP_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["OCP_Workflow"]
                if "RelationshipType" in currentlyAvaliableWorkflows[uip["Workflow"]]:
                    currentWorkflowDetails = currentlyAvaliableWorkflows[uip["Workflow"]]
                    if uip["RelationshipType"] and (currentWorkflowDetails["RelationshipType"] != uip["RelationshipType"]):
                        msg="selected relation "+ uip["RelationshipType"] + " is not valid." + rowStr
                        inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                        continue

                # another temporary check which is not required if all the parameters of workflow  were  properly handed off from TS
                if "RelationshipType" not in uip :
                    msg="INTERNAL ERROR:  For selected workflow "+ uip["Workflow"] + ", an internal key  RelationshipType is missing for row " + rowStr
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue

                #bring in all the workflow parameter so far available, into the uip hash.
                for k in  currentlyAvaliableWorkflows[uip["Workflow"]] :
                    uip[k] = currentlyAvaliableWorkflows[uip["Workflow"]][k]

                #Override cellularity percentage based on DNA RNA workflows
                if (uip["DNA_RNA_Workflow"] == "DNA_RNA"):
                    if (uip["nucleotideType"] == "DNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "1"
                    elif (uip["nucleotideType"] == "RNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "0"
            else:
                uip["ApplicationType"] = "unknown"
                msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time" + rowStr
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                continue
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""
        if  "cellularityPct" in uip :
            uip["CellularityPct"] = uip["cellularityPct"]
        if  "CellularityPct" not in uip :
            uip["CellularityPct"] = ""
        if  "cancerType" in uip :
            uip["CancerType"] = uip["cancerType"]
        if  "CancerType" not in uip :
            uip["CancerType"] = ""
        if  "controlType" in uip :
            if uip["controlType"] == "None":
                uip["ControlType"] = ""
            else:
                uip["ControlType"] = uip["controlType"]
        if  "controlType" not in uip :
            uip["ControlType"] = ""
        if  "reference" in uip :
            uip["Reference"] = uip["reference"]
        if  "reference" not in uip :
            uip["Reference"] = ""
        if  "hotSpotRegionBedFile" in uip :
            uip["HotSpotRegionBedFile"] = uip["hotSpotRegionBedFile"]
        if  "hotSpotRegionBedFile" not in uip :
            uip["HotSpotRegionBedFile"] = ""
        if  "targetRegionBedFile" in uip :
            uip["TargetRegionBedFile"] = uip["targetRegionBedFile"]
        if  "targetRegionBedFile" not in uip :
            uip["TargetRegionBedFile"] = ""
            

        if(uip["CancerType"] and (uip["CancerType"] not in cancerTypesList)):
            msg="selected cancer type "+ uip["CancerType"] + " is not valid for this IR user account. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["Gender"] and (uip["Gender"] not in validGenderList)):
            msg="selected gender type "+ uip["Gender"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["RelationRole"] and (uip["RelationRole"] not in validRelations)):
            msg="selected relation role "+ uip["RelationRole"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            continue

        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = uip  #later if its a three level then make it into an array of uips
        else:
            duplicateSamplesExists = True
            theOtherUip = uniqueSamples[uip["sample"]]
            theOtherRowStr = theOtherUip["row"]
            theOtherSetid = theOtherUip["setid"]
            theOtherRelation = theOtherUip["Relation"]
            theOtherRelationShipType = theOtherUip["RelationshipType"]
            theOtherGender = theOtherUip["Gender"]
            if  "controlType" in theOtherUip :
                if theOtherUip["controlType"] == "None":
                    theOtherUipControlType = ""
                else:
                    theOtherUipControlType = theOtherUip["controlType"]
            if  "controlType" not in theOtherUip :
                theOtherUipControlType = ""
            if  "reference" in theOtherUip :
                theOtherUipReference = theOtherUip["reference"]
            if  "reference" not in theOtherUip :
                theOtherUipReference = ""
            if  "hotSpotRegionBedFile" in theOtherUip :
                theOtherUipHotSpotRegionBedFile = theOtherUip["hotSpotRegionBedFile"]
            if  "hotSpotRegionBedFile" not in theOtherUip :
                theOtherUipHotSpotRegionBedFile = ""
            if  "targetRegionBedFile" in theOtherUip :
                theOtherUipTargetRegionBedFile = theOtherUip["targetRegionBedFile"]
            if  "targetRegionBedFile" not in theOtherUip :
                theOtherUipTargetRegionBedFile = ""

            write_debug_log("OtherSetid: " + theOtherSetid + ", theOtherRelation: " + theOtherRelation + ", theOtherRelationShipType: " + theOtherRelationShipType + ", theOtherGender: " + theOtherGender + ", theOtherControlType: " + theOtherUipControlType + ", theOtherUipReference: " + theOtherUipReference + ", theOtherUipHotSpotRegionBedFile: " + theOtherUipHotSpotRegionBedFile + ", theOtherUipTargetRegionBedFile: " + theOtherUipTargetRegionBedFile)
            write_debug_log("this Setid: " + uip["setid"] + ", Relation: " + uip["Relation"] + ", RelationshipType: " + uip["RelationshipType"] + ", Gender: " + uip["Gender"] + ", ControlType: " + uip["ControlType"] + ", Reference: " + uip["Reference"] + ", HotSpotRegionBedFile: " + uip["HotSpotRegionBedFile"] + ", TargetRegionBedFile: " + uip["TargetRegionBedFile"])

            theOtherDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in theOtherUip:
                theOtherDNA_RNA_Workflow = theOtherUip["DNA_RNA_Workflow"]
            thisDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in uip:
                thisDNA_RNA_Workflow = uip["DNA_RNA_Workflow"]
            theOtherNucleotideType = ""
            if "NucleotideType" in theOtherUip:
                theOtherNucleotideType = theOtherUip["NucleotideType"]
            thisNucleotideType = ""
            if "NucleotideType" in uip:
                thisNucleotideType = uip["NucleotideType"]
            # if the rows are for DNA_RNA workflow, then dont complain .. just pass it along..
            #debug print  uip["row"] +" == " + theOtherRowStr + " samplename similarity  " + uip["DNA_RNA_Workflow"] + " == "+ theOtherDNA_RNA_Workflow
            if (       ((uip["Workflow"]=="Upload Only")or(uip["Workflow"] == "")) and (thisNucleotideType != theOtherNucleotideType)     ):
                duplicateSamplesExists = False
            if (       (uip["setid"] == theOtherSetid) and (thisDNA_RNA_Workflow == theOtherDNA_RNA_Workflow ) and (thisDNA_RNA_Workflow == "DNA_RNA")      ):
                duplicateSamplesExists = False

            fieldValueDiffers = False
            if (uip["setid"] != theOtherSetid):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)      # TDB: Highlighting fields in these below conditions is not working, Check later.
            if (uip["Relation"] != theOtherRelation):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Relation", rowHighlightableFields)
            if (uip["RelationshipType"] != theOtherRelationShipType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
            if (uip["Gender"] != theOtherGender):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Gender", rowHighlightableFields)
            if (uip["ControlType"] != theOtherUipControlType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "ControlType", rowHighlightableFields)
            if (uip["Reference"] != theOtherUipReference):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Reference", rowHighlightableFields)
            if (uip["HotSpotRegionBedFile"] != theOtherUipHotSpotRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "HotSpotRegionBedFile", rowHighlightableFields)
            if (uip["TargetRegionBedFile"] != theOtherUipTargetRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "TargetRegionBedFile", rowHighlightableFields)

            if not fieldValueDiffers:
                duplicateSamplesExists = False


            if duplicateSamplesExists :
                msg ="Sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+theOtherRowStr+", Please change the sample name. Or, If you intend to use multi-barcodes per sample then please make sure all the other field values are same for all corresponding rows."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
                continue
            # else dont flag an error

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True
            if (  (isVariantCallerSelected != "Unknown")  and (isVariantCallerConfigured != "Unknown")  ):
                if (isVariantCallerSelected != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. Please select and configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue
                if (isVariantCallerConfigured != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. The Variant Caller plugin is selected, but not configured. Please configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
            continue
        # save the workflow information of the record on the setID.. also check workflow mismatch with previous row of the same setid
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[]
            setidHash[setid]["firstRecordRow"]=uip["row"]
            if uip["Workflow"] == "":
                setidHash[setid]["firstWorkflow"]=""
                setidHash[setid]["firstApplicationType"]=""
                setidHash[setid]["firstRelationshipType"]=""
                setidHash[setid]["firstRecordDNA_RNA"]=""
            else:
                setidHash[setid]["firstWorkflow"]=uip["Workflow"]
                setidHash[setid]["firstApplicationType"]=uip["ApplicationType"]
                setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
                setidHash[setid]["firstRecordDNA_RNA"]=uip["DNA_RNA_Workflow"]
            if "AllowMultipleRoleRecords" in uip :
                setidHash[setid]["firstAllowMultipleRoleRecords"]=uip["AllowMultipleRoleRecords"]
        else:
            previousRow = setidHash[setid]["firstRecordRow"]
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            expectedRelationshipType = setidHash[setid]["firstRelationshipType"]
            expectedApplicationType = setidHash[setid]["firstApplicationType"]
            #print  uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
            if expectedWorkflow != uip["Workflow"]:
                msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
            elif expectedRelationshipType != uip["RelationshipType"]:
                #print  "error on " + uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
                msg="INTERNAL ERROR:  RelationshipType "+ uip["RelationshipType"] + " of the selected workflow, does not match a previous sample with the same SetID, with RelationshipType "+ expectedRelationshipType +" in row "+ previousRow+ "."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #elif expectedApplicationType != uip["ApplicationType"]:  #TBD add similar internal error
        setidHash[setid]["records"].append(uip)

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"] = uip["sample"]
        if uip["sample"] not in uniqueSamples:    # no need to repeat if the check has been done for the same sample name on an earlier row.
            sampleExistsCallResults = sampleExistsOnIR(inputJson)
            if sampleExistsCallResults.get("error") != "":
                if sampleExistsCallResults.get("status") == "true":
                    msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)

        # check all the generic rules for this uip .. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_5_6(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields)

        row = row + 1


    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the given set of records of the set
        rowsLooked = ""
        uniqueSamplesForThisSetID = []
        for record in setidHash[setid]["records"]:
            if record["sample"] not in uniqueSamplesForThisSetID:
                uniqueSamplesForThisSetID.append(record["sample"])
            

        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)
            # check if any extra roles exists.  Given that the above test exists for lack of roles, it is sufficient if we 
            # verify the total number of roles expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of roles required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            numRecordsForThisSetId = len(setidHash[setid]["records"])
            numOfUniqueSamples = len(uniqueSamplesForThisSetID)
            singleSampleApplicationTypeSet = set(["Amplicon Sequencing","Amplicon Low Frequency Sequencing","Low-Coverage Whole Genome Sequencing","Oncomine_RNA_Fusion","Annotation","Targeted Resequencing", \
                                                "AmpliSeqHD Single Pool","Low Frequency Resequencing","Mutational Load","ONCOLOGY_LIQUID_BIOPSY","ImmuneRepertoire","Genomic Resequencing"])
            if ( (setidHash[setid]["firstApplicationType"] in singleSampleApplicationTypeSet) and (numOfUniqueSamples > sizeOfRequiredRoles)) :
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of samples are found. Expected number of samples is " + str(sizeOfRequiredRoles) + ". "
                if   rowsLooked != "" :
                     if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                     else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Sample", rowHighlightableFields)  

            if (numRecordsForThisSetId > sizeOfRequiredRoles):
                complainAboutTooManyRoles = True

                uniqueRoles = []
                for uipInRecords in setidHash[setid]["records"]:
                    if (uipInRecords["Relation"] not in uniqueRoles):
                        uniqueRoles.append(uipInRecords["Relation"])
                if(len(uniqueRoles) == sizeOfRequiredRoles):
                    complainAboutTooManyRoles = False

                # ignore this check if the application type or other workflow settings already allws multi roles
                if "firstAllowMultipleRoleRecords" in setidHash[setid]:
                    if setidHash[setid]["firstAllowMultipleRoleRecords"] == "true":
                        complainAboutTooManyRoles = False
                # for DNA_RNA flag, its not the roles to be evaluated, its the nucleotideTypes to be evaluated.
                if setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA":
                    complainAboutTooManyRoles = False

                if complainAboutTooManyRoles:
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of RelationRoles is found. Expected number of roles is " + str(sizeOfRequiredRoles) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)

        ##
        # validate the nucleotidetypes, similar to the roles.
        # first check all the required nucleotides are there in the given set of records of the set
        #    Use the value of the rowsLooked,  populated from the above loop.
        if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")   ): 
            for validNucloetide in setidHash[setid]["validNucleotideTypes"]:
                foundNucleotide=0
                for record in setidHash[setid]["records"]:
                    if validNucloetide == record["NucleotideType"]:   #or NucleotideType
                        foundNucleotide = 1
                if foundNucleotide == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required NucleotideType "+ validNucloetide + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)
            # check if any extra nucleotides exists.  Given that the above test exists for missing nucleotides, it is sufficient if we 
            # verify the total number of nucleotides expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of nucleotides required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredNucleotides = len(setidHash[setid]["validNucleotideTypes"])
            numberOfUniqueSamples = len(uniqueSamplesForThisSetID)
            #numRecordsForThisSetId = len(setidHash[setid]["records"])   #already done as part of roles check
            if (numberOfUniqueSamples > sizeOfRequiredNucleotides):
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of Nucleotides is found. Expected number of Nucleotides is " + str(sizeOfRequiredNucleotides) + ". "
                if   rowsLooked != "" :
                    if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                    else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)


        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."





    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
           for e in  rowErrors[rowstr]:
              foundAtLeastOneError =1
              emsg = emsg + e + " ; "
        if rowstr in rowWarnings:
           for w in  rowWarnings[rowstr]:
              wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        if rowstr in rowHighlightableFields:
           k["highlightableFields"]=rowHighlightableFields[rowstr]
        else:
           k["highlightableFields"]=[]
        validationResults.append(k)

    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin


    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
           "conditions": conditions
           }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """

def validateAllRulesOnRecord_5_6(rules, uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                #msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                #inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                continue

            andForExists = 0
            if "AndFor" in rule:
                if rule["AndFor"]["Name"] not in uip:
                    continue
                else:
                    andForExists = 1

            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1
                    if valueCheck == 1 :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kValid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
                        # another small hardcoded update into the setidHash for later evaluation of the nucleotideType  uniqueness
                        if kValid == "NucleotideType":
                            if setid  in setidHash:
                                if "validNucleotideTypes" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validNucleotideTypes"] = vValid   # this is actually list of valid nucleotideTypes
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if valueCheck == 1 :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kInvalid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "NonEmpty" in rule:
                kFor=rule["For"]["Name"]
                vFor=rule["For"]["Value"]
                kNonEmpty=rule["NonEmpty"]["Name"]
                #print  "non empty validating   kfor " +kFor  + " vFor "+ vFor + "  kNonEmpty "+ kNonEmpty
                #if kFor not in uip :
                #    print  "kFor not in uip   "  + " kFor "+ kFor 
                #    continue
                if uip[kFor] == vFor :
                    if (   (kNonEmpty not in uip)   or  (uip[kNonEmpty] == "")   ):
                        #msg="Empty value found for " + kNonEmpty + " When "+ kFor + " is \"" + vFor +"\"."
                        msg="Empty value found for " + kNonEmpty
                        inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(row, kNonEmpty, rowHighlightableFields)
                        inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "Disabled" in rule:
                pass
            else:
                 msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                 inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

def validateUserInput_5_10(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"

    #variantCaller check variables
    requiresVariantCallerPlugin = False
    isVariantCallerSelected = "Unknown"
    if "isVariantCallerSelected" in userInput:
        isVariantCallerSelected = userInput["isVariantCallerSelected"]
    isVariantCallerConfigured = "Unknown"
    if "isVariantCallerConfigured" in userInput:
        isVariantCallerConfigured = userInput["isVariantCallerConfigured"]

    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    authCheckResult = authCheck(inputJson) 
    #if authCheckResult.get("status") == "false":
    if (   (authCheckResult["status"] !="true")  or (authCheckResult["error"] != "none")   ):
        return {"status": "true",
                "error": "Authentication Failure",
                "validationResults": []}

    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []

    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
       currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
       orderedColumns[col["Order"]] = col

    # Get cancer types
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    # Extracting Gender column from the current rules for validation purpose. 
    validGenderList = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Gender"):
            validGenderList = col["Values"]

    # Extracting Relation column from the current rules for validation purpose.
    validRelations = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Relation"):
            validRelations = col["Values"]

    # getting the complete workflow list to extract the relationship type.
    allWorkflowListResult = getWorkflowList(inputJson)
    if (allWorkflowListResult["status"] != "true"):
        return allWorkflowListResult
    allWorkflowList = allWorkflowListResult["userWorkflows"]

    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """


    ###################################### This is a mock logic. This is not the real validation code. This is for test only
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
               resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    rowHighlightableFields={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]

    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
           uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets.  Also do the same for highlightableFields
        if  rowStr not in rowErrors:
           rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
           rowWarnings[rowStr]=[]
        if  rowStr not in rowHighlightableFields:
           rowHighlightableFields[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"] = uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"] = uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"] = uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if uip["Workflow"] !="":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                #uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
                #uip["DNA_RNA_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["DNA_RNA_Workflow"]
                #uip["OCP_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["OCP_Workflow"]
                if "RelationshipType" in currentlyAvaliableWorkflows[uip["Workflow"]]:
                    currentWorkflowDetails = currentlyAvaliableWorkflows[uip["Workflow"]]
                    if uip["RelationshipType"] and (currentWorkflowDetails["RelationshipType"] != uip["RelationshipType"]):
                        msg="selected relation "+ uip["RelationshipType"] + " is not valid." + rowStr
                        inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                        continue

                # another temporary check which is not required if all the parameters of workflow  were  properly handed off from TS
                if "RelationshipType" not in uip :
                    msg="INTERNAL ERROR:  For selected workflow "+ uip["Workflow"] + ", an internal key  RelationshipType is missing for row " + rowStr
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue

                #bring in all the workflow parameter so far available, into the uip hash.
                for k in  currentlyAvaliableWorkflows[uip["Workflow"]] :
                    uip[k] = currentlyAvaliableWorkflows[uip["Workflow"]][k]

                #Override cellularity percentage based on DNA RNA workflows
                if (uip["DNA_RNA_Workflow"] == "DNA_RNA"):
                    if (uip["nucleotideType"] == "DNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "1"
                    elif (uip["nucleotideType"] == "RNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "0"

                if ("tag_NO_CNV" in uip and uip["tag_NO_CNV"] == "true"):
                    uip["CELLULARITY_PCT_REQUIRED"] = "0"

                if ("tag_TAGSEQ" in uip and uip["tag_TAGSEQ"] == "true"):
                    uip["CELLULARITY_PCT_REQUIRED"] = "0"

            else:
                uip["ApplicationType"] = "unknown"
                msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time" + rowStr
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                continue
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""
        if  "cellularityPct" in uip :
            uip["CellularityPct"] = uip["cellularityPct"]
        if  "CellularityPct" not in uip :
            uip["CellularityPct"] = ""
        if  "cancerType" in uip :
            uip["CancerType"] = uip["cancerType"]
        if  "CancerType" not in uip :
            uip["CancerType"] = ""
        if  "controlType" in uip :
            if uip["controlType"] == "None":
                uip["ControlType"] = ""
            else:
                uip["ControlType"] = uip["controlType"]
        if  "controlType" not in uip :
            uip["ControlType"] = ""
        if  "reference" in uip :
            uip["Reference"] = uip["reference"]
        if  "reference" not in uip :
            uip["Reference"] = ""
        if  "hotSpotRegionBedFile" in uip :
            uip["HotSpotRegionBedFile"] = uip["hotSpotRegionBedFile"]
        if  "hotSpotRegionBedFile" not in uip :
            uip["HotSpotRegionBedFile"] = ""
        if  "targetRegionBedFile" in uip :
            uip["TargetRegionBedFile"] = uip["targetRegionBedFile"]
        if  "targetRegionBedFile" not in uip :
            uip["TargetRegionBedFile"] = ""
            

        if(uip["CancerType"] and (uip["CancerType"] not in cancerTypesList)):
            msg="selected cancer type "+ uip["CancerType"] + " is not valid for this IR user account. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["Gender"] and (uip["Gender"] not in validGenderList)):
            msg="selected gender type "+ uip["Gender"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["RelationRole"] and (uip["RelationRole"] not in validRelations)):
            msg="selected relation role "+ uip["RelationRole"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            continue

        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = uip  #later if its a three level then make it into an array of uips
        else:
            duplicateSamplesExists = True
            theOtherUip = uniqueSamples[uip["sample"]]
            theOtherRowStr = theOtherUip["row"]
            theOtherSetid = theOtherUip["setid"]
            theOtherRelation = theOtherUip["Relation"]
            theOtherRelationShipType = theOtherUip["RelationshipType"]
            theOtherGender = theOtherUip["Gender"]
            if  "controlType" in theOtherUip :
                if theOtherUip["controlType"] == "None":
                    theOtherUipControlType = ""
                else:
                    theOtherUipControlType = theOtherUip["controlType"]
            if  "controlType" not in theOtherUip :
                theOtherUipControlType = ""
            if  "reference" in theOtherUip :
                theOtherUipReference = theOtherUip["reference"]
            if  "reference" not in theOtherUip :
                theOtherUipReference = ""
            if  "hotSpotRegionBedFile" in theOtherUip :
                theOtherUipHotSpotRegionBedFile = theOtherUip["hotSpotRegionBedFile"]
            if  "hotSpotRegionBedFile" not in theOtherUip :
                theOtherUipHotSpotRegionBedFile = ""
            if  "targetRegionBedFile" in theOtherUip :
                theOtherUipTargetRegionBedFile = theOtherUip["targetRegionBedFile"]
            if  "targetRegionBedFile" not in theOtherUip :
                theOtherUipTargetRegionBedFile = ""

            write_debug_log("OtherSetid: " + theOtherSetid + ", theOtherRelation: " + theOtherRelation + ", theOtherRelationShipType: " + theOtherRelationShipType + ", theOtherGender: " + theOtherGender + ", theOtherControlType: " + theOtherUipControlType + ", theOtherUipReference: " + theOtherUipReference + ", theOtherUipHotSpotRegionBedFile: " + theOtherUipHotSpotRegionBedFile + ", theOtherUipTargetRegionBedFile: " + theOtherUipTargetRegionBedFile)
            write_debug_log("this Setid: " + uip["setid"] + ", Relation: " + uip["Relation"] + ", RelationshipType: " + uip["RelationshipType"] + ", Gender: " + uip["Gender"] + ", ControlType: " + uip["ControlType"] + ", Reference: " + uip["Reference"] + ", HotSpotRegionBedFile: " + uip["HotSpotRegionBedFile"] + ", TargetRegionBedFile: " + uip["TargetRegionBedFile"])

            theOtherDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in theOtherUip:
                theOtherDNA_RNA_Workflow = theOtherUip["DNA_RNA_Workflow"]
            thisDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in uip:
                thisDNA_RNA_Workflow = uip["DNA_RNA_Workflow"]
            theOtherNucleotideType = ""
            if "NucleotideType" in theOtherUip:
                theOtherNucleotideType = theOtherUip["NucleotideType"]
            thisNucleotideType = ""
            if "NucleotideType" in uip:
                thisNucleotideType = uip["NucleotideType"]
            # if the rows are for DNA_RNA workflow, then dont complain .. just pass it along..
            #debug print  uip["row"] +" == " + theOtherRowStr + " samplename similarity  " + uip["DNA_RNA_Workflow"] + " == "+ theOtherDNA_RNA_Workflow
            if (       ((uip["Workflow"]=="Upload Only")or(uip["Workflow"] == "")) and (thisNucleotideType != theOtherNucleotideType)     ):
                duplicateSamplesExists = False
            if (       (uip["setid"] == theOtherSetid) and (thisDNA_RNA_Workflow == theOtherDNA_RNA_Workflow ) and (thisDNA_RNA_Workflow == "DNA_RNA")      ):
                duplicateSamplesExists = False

            fieldValueDiffers = False
            if (uip["setid"] != theOtherSetid):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)      # TDB: Highlighting fields in these below conditions is not working, Check later.
            if (uip["Relation"] != theOtherRelation):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Relation", rowHighlightableFields)
            if (uip["RelationshipType"] != theOtherRelationShipType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
            if (uip["Gender"] != theOtherGender):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Gender", rowHighlightableFields)
            if (uip["ControlType"] != theOtherUipControlType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "ControlType", rowHighlightableFields)
            if (uip["Reference"] != theOtherUipReference):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Reference", rowHighlightableFields)
            if (uip["HotSpotRegionBedFile"] != theOtherUipHotSpotRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "HotSpotRegionBedFile", rowHighlightableFields)
            if (uip["TargetRegionBedFile"] != theOtherUipTargetRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "TargetRegionBedFile", rowHighlightableFields)

            if not fieldValueDiffers:
                duplicateSamplesExists = False


            if duplicateSamplesExists :
                msg ="Sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+theOtherRowStr+", Please change the sample name. Or, If you intend to use multi-barcodes per sample then please make sure all the other field values are same for all corresponding rows."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
                continue
            # else dont flag an error

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True
            if (  (isVariantCallerSelected != "Unknown")  and (isVariantCallerConfigured != "Unknown")  ):
                if (isVariantCallerSelected != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. Please select and configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue
                if (isVariantCallerConfigured != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. The Variant Caller plugin is selected, but not configured. Please configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
            continue
        # save the workflow information of the record on the setID.. also check workflow mismatch with previous row of the same setid
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[]
            setidHash[setid]["firstRecordRow"]=uip["row"]
            if uip["Workflow"] == "":
                setidHash[setid]["firstWorkflow"]=""
                setidHash[setid]["firstApplicationType"]=""
                setidHash[setid]["firstRelationshipType"]=""
                setidHash[setid]["firstRecordDNA_RNA"]=""
            else:
                setidHash[setid]["firstWorkflow"]=uip["Workflow"]
                setidHash[setid]["firstApplicationType"]=uip["ApplicationType"]
                setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
                setidHash[setid]["firstRecordDNA_RNA"]=uip["DNA_RNA_Workflow"]
            if "AllowMultipleRoleRecords" in uip :
                setidHash[setid]["firstAllowMultipleRoleRecords"]=uip["AllowMultipleRoleRecords"]
        else:
            previousRow = setidHash[setid]["firstRecordRow"]
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            expectedRelationshipType = setidHash[setid]["firstRelationshipType"]
            expectedApplicationType = setidHash[setid]["firstApplicationType"]
            #print  uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
            if expectedWorkflow != uip["Workflow"]:
                msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
            elif expectedRelationshipType != uip["RelationshipType"]:
                #print  "error on " + uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
                msg="INTERNAL ERROR:  RelationshipType "+ uip["RelationshipType"] + " of the selected workflow, does not match a previous sample with the same SetID, with RelationshipType "+ expectedRelationshipType +" in row "+ previousRow+ "."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #elif expectedApplicationType != uip["ApplicationType"]:  #TBD add similar internal error
        setidHash[setid]["records"].append(uip)

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"] = uip["sample"]
        if uip["sample"] not in uniqueSamples:    # no need to repeat if the check has been done for the same sample name on an earlier row.
            sampleExistsCallResults = sampleExistsOnIR(inputJson)
            if sampleExistsCallResults.get("error") != "":
                if sampleExistsCallResults.get("status") == "true":
                    msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)

        # check all the generic rules for this uip .. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_5_10(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields)

        row = row + 1


    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the given set of records of the set
        rowsLooked = ""
        uniqueSamplesForThisSetID = []

        for record in setidHash[setid]["records"]:
            if record["sample"] not in uniqueSamplesForThisSetID:
                uniqueSamplesForThisSetID.append(record["sample"])
            

        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)
            # check if any extra roles exists.  Given that the above test exists for lack of roles, it is sufficient if we 
            # verify the total number of roles expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of roles required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            numRecordsForThisSetId = len(setidHash[setid]["records"])
            numOfUniqueSamples = len(uniqueSamplesForThisSetID)
            singleSampleApplicationTypeSet = set(["Amplicon Sequencing","Amplicon Low Frequency Sequencing","Low-Coverage Whole Genome Sequencing","Oncomine_RNA_Fusion","Annotation","Targeted Resequencing", \
                                                "AmpliSeqHD Single Pool","Low Frequency Resequencing","Mutational Load","ONCOLOGY_LIQUID_BIOPSY","ImmuneRepertoire","Genomic Resequencing"])
            if ( (setidHash[setid]["firstApplicationType"] in singleSampleApplicationTypeSet) and (numOfUniqueSamples > sizeOfRequiredRoles)) :
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of samples are found. Expected number of samples is " + str(sizeOfRequiredRoles) + ". "
                if   rowsLooked != "" :
                     if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                     else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Sample", rowHighlightableFields)  

            if (numRecordsForThisSetId > sizeOfRequiredRoles):
                complainAboutTooManyRoles = True

                uniqueRoles = []
                for uipInRecords in setidHash[setid]["records"]:
                    if (uipInRecords["Relation"] not in uniqueRoles):
                        uniqueRoles.append(uipInRecords["Relation"])
                if(len(uniqueRoles) == sizeOfRequiredRoles):
                    complainAboutTooManyRoles = False

                # ignore this check if the application type or other workflow settings already allws multi roles
                if "firstAllowMultipleRoleRecords" in setidHash[setid]:
                    if setidHash[setid]["firstAllowMultipleRoleRecords"] == "true":
                        complainAboutTooManyRoles = False
                # for DNA_RNA flag, its not the roles to be evaluated, its the nucleotideTypes to be evaluated.
                if setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA":
                    complainAboutTooManyRoles = False

                if complainAboutTooManyRoles:
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of RelationRoles is found. Expected number of roles is " + str(sizeOfRequiredRoles) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)

        ##
        # validate the nucleotidetypes, similar to the roles.
        # first check all the required nucleotides are there in the given set of records of the set
        #    Use the value of the rowsLooked,  populated from the above loop.
        if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")   ): 
            for validNucloetide in setidHash[setid]["validNucleotideTypes"]:
                foundNucleotide=0
                for record in setidHash[setid]["records"]:
                    if validNucloetide == record["NucleotideType"]:   #or NucleotideType
                        foundNucleotide = 1
                if foundNucleotide == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required NucleotideType "+ validNucloetide + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)
            # check if any extra nucleotides exists.  Given that the above test exists for missing nucleotides, it is sufficient if we 
            # verify the total number of nucleotides expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of nucleotides required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredNucleotides = len(setidHash[setid]["validNucleotideTypes"])
            numberOfUniqueSamples = len(uniqueSamplesForThisSetID)
            #numRecordsForThisSetId = len(setidHash[setid]["records"])   #already done as part of roles check
            if (numberOfUniqueSamples > sizeOfRequiredNucleotides):
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of Nucleotides is found. Expected number of Nucleotides is " + str(sizeOfRequiredNucleotides) + ". "
                if   rowsLooked != "" :
                    if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                    else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)


        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."





    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
           for e in  rowErrors[rowstr]:
              foundAtLeastOneError =1
              emsg = emsg + e + " ; "
        if rowstr in rowWarnings:
           for w in  rowWarnings[rowstr]:
              wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        if rowstr in rowHighlightableFields:
           k["highlightableFields"]=rowHighlightableFields[rowstr]
        else:
           k["highlightableFields"]=[]
        validationResults.append(k)

    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin


    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
           "conditions": conditions
           }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """

def validateAllRulesOnRecord_5_10(rules, uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                #msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                #inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                continue

            andForExists = 0
            if "AndFor" in rule:
                if rule["AndFor"]["Name"] not in uip:
                    continue
                else:
                    andForExists = 1

            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1
                    if valueCheck == 1 :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kValid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
                        # another small hardcoded update into the setidHash for later evaluation of the nucleotideType  uniqueness
                        if kValid == "NucleotideType":
                            if setid  in setidHash:
                                if "validNucleotideTypes" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validNucleotideTypes"] = vValid   # this is actually list of valid nucleotideTypes
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if valueCheck == 1 :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kInvalid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "NonEmpty" in rule:
                kFor=rule["For"]["Name"]
                vFor=rule["For"]["Value"]
                kNonEmpty=rule["NonEmpty"]["Name"]
                #print  "non empty validating   kfor " +kFor  + " vFor "+ vFor + "  kNonEmpty "+ kNonEmpty
                #if kFor not in uip :
                #    print  "kFor not in uip   "  + " kFor "+ kFor 
                #    continue
                if uip[kFor] == vFor :
                    if (   (kNonEmpty not in uip)   or  (uip[kNonEmpty] == "")   ):
                        #msg="Empty value found for " + kNonEmpty + " When "+ kFor + " is \"" + vFor +"\"."
                        msg="Empty value found for " + kNonEmpty
                        inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(row, kNonEmpty, rowHighlightableFields)
                        inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "Disabled" in rule:
                pass
            else:
                 msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                 inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

def validateUserInput_5_12(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"

    #variantCaller check variables
    requiresVariantCallerPlugin = False
    isVariantCallerSelected = "Unknown"
    if "isVariantCallerSelected" in userInput:
        isVariantCallerSelected = userInput["isVariantCallerSelected"]
    isVariantCallerConfigured = "Unknown"
    if "isVariantCallerConfigured" in userInput:
        isVariantCallerConfigured = userInput["isVariantCallerConfigured"]

    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    authCheckResult = authCheck(inputJson) 
    #if authCheckResult.get("status") == "false":
    if (   (authCheckResult["status"] !="true")  or (authCheckResult["error"] != "none")   ):
        return {"status": "true",
                "error": "Authentication Failure",
                "validationResults": []}

    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []

    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
       currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
       orderedColumns[col["Order"]] = col

    # Get cancer types
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    # Extracting Gender column from the current rules for validation purpose. 
    validGenderList = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Gender"):
            validGenderList = col["Values"]

    # Extracting Relation column from the current rules for validation purpose.
    validRelations = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Relation"):
            validRelations = col["Values"]

    # getting the complete workflow list to extract the relationship type.
    allWorkflowListResult = getWorkflowList(inputJson)
    if (allWorkflowListResult["status"] != "true"):
        return allWorkflowListResult
    allWorkflowList = allWorkflowListResult["userWorkflows"]

    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """


    ###################################### This is a mock logic. This is not the real validation code. This is for test only
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
               resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    rowHighlightableFields={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]

    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
           uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets.  Also do the same for highlightableFields
        if  rowStr not in rowErrors:
           rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
           rowWarnings[rowStr]=[]
        if  rowStr not in rowHighlightableFields:
           rowHighlightableFields[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"] = uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"] = uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"] = uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if uip["Workflow"] !="":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                #uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
                #uip["DNA_RNA_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["DNA_RNA_Workflow"]
                #uip["OCP_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["OCP_Workflow"]
                if "RelationshipType" in currentlyAvaliableWorkflows[uip["Workflow"]]:
                    currentWorkflowDetails = currentlyAvaliableWorkflows[uip["Workflow"]]
                    if uip["RelationshipType"] and (currentWorkflowDetails["RelationshipType"] != uip["RelationshipType"]):
                        msg="selected relation "+ uip["RelationshipType"] + " is not valid." + rowStr
                        inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                        continue

                # another temporary check which is not required if all the parameters of workflow  were  properly handed off from TS
                if "RelationshipType" not in uip :
                    msg="INTERNAL ERROR:  For selected workflow "+ uip["Workflow"] + ", an internal key  RelationshipType is missing for row " + rowStr
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue

                #bring in all the workflow parameter so far available, into the uip hash.
                for k in  currentlyAvaliableWorkflows[uip["Workflow"]] :
                    uip[k] = currentlyAvaliableWorkflows[uip["Workflow"]][k]

                #Override cellularity percentage based on DNA RNA workflows
                if (uip["DNA_RNA_Workflow"] == "DNA_RNA"):
                    if (uip["nucleotideType"] == "DNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "1"
                    elif (uip["nucleotideType"] == "RNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "0"

                if ("tag_NO_CNV" in uip and uip["tag_NO_CNV"] == "true"):
                    uip["CELLULARITY_PCT_REQUIRED"] = "0"

                if ("tag_TAGSEQ" in uip and uip["tag_TAGSEQ"] == "true"):
                    uip["CELLULARITY_PCT_REQUIRED"] = "0"

            else:
                uip["ApplicationType"] = "unknown"
                msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time" + rowStr
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                continue
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""
        if  "cellularityPct" in uip :
            uip["CellularityPct"] = uip["cellularityPct"]
        if  "CellularityPct" not in uip :
            uip["CellularityPct"] = ""
        if  "cancerType" in uip :
            uip["CancerType"] = uip["cancerType"]
        if  "CancerType" not in uip :
            uip["CancerType"] = ""
        if  "controlType" in uip :
            if uip["controlType"] == "None":
                uip["ControlType"] = ""
            else:
                uip["ControlType"] = uip["controlType"]
        if  "controlType" not in uip :
            uip["ControlType"] = ""
        if  "reference" in uip :
            uip["Reference"] = uip["reference"]
        if  "reference" not in uip :
            uip["Reference"] = ""
        if  "hotSpotRegionBedFile" in uip :
            uip["HotSpotRegionBedFile"] = uip["hotSpotRegionBedFile"]
        if  "hotSpotRegionBedFile" not in uip :
            uip["HotSpotRegionBedFile"] = ""
        if  "targetRegionBedFile" in uip :
            uip["TargetRegionBedFile"] = uip["targetRegionBedFile"]
        if  "targetRegionBedFile" not in uip :
            uip["TargetRegionBedFile"] = ""
            

        if(uip["CancerType"] and (uip["CancerType"] not in cancerTypesList)):
            msg="selected cancer type "+ uip["CancerType"] + " is not valid for this IR user account. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["Gender"] and (uip["Gender"] not in validGenderList)):
            msg="selected gender type "+ uip["Gender"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["RelationRole"] and (uip["RelationRole"] not in validRelations)):
            msg="selected relation role "+ uip["RelationRole"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            continue

        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = uip  #later if its a three level then make it into an array of uips
        else:
            duplicateSamplesExists = True
            theOtherUip = uniqueSamples[uip["sample"]]
            theOtherRowStr = theOtherUip["row"]
            theOtherSetid = theOtherUip["setid"]
            theOtherRelation = theOtherUip["Relation"]
            theOtherRelationShipType = theOtherUip["RelationshipType"]
            theOtherGender = theOtherUip["Gender"]
            if  "controlType" in theOtherUip :
                if theOtherUip["controlType"] == "None":
                    theOtherUipControlType = ""
                else:
                    theOtherUipControlType = theOtherUip["controlType"]
            if  "controlType" not in theOtherUip :
                theOtherUipControlType = ""
            if  "reference" in theOtherUip :
                theOtherUipReference = theOtherUip["reference"]
            if  "reference" not in theOtherUip :
                theOtherUipReference = ""
            if  "hotSpotRegionBedFile" in theOtherUip :
                theOtherUipHotSpotRegionBedFile = theOtherUip["hotSpotRegionBedFile"]
            if  "hotSpotRegionBedFile" not in theOtherUip :
                theOtherUipHotSpotRegionBedFile = ""
            if  "targetRegionBedFile" in theOtherUip :
                theOtherUipTargetRegionBedFile = theOtherUip["targetRegionBedFile"]
            if  "targetRegionBedFile" not in theOtherUip :
                theOtherUipTargetRegionBedFile = ""

            write_debug_log("OtherSetid: " + theOtherSetid + ", theOtherRelation: " + theOtherRelation + ", theOtherRelationShipType: " + theOtherRelationShipType + ", theOtherGender: " + theOtherGender + ", theOtherControlType: " + theOtherUipControlType + ", theOtherUipReference: " + theOtherUipReference + ", theOtherUipHotSpotRegionBedFile: " + theOtherUipHotSpotRegionBedFile + ", theOtherUipTargetRegionBedFile: " + theOtherUipTargetRegionBedFile)
            write_debug_log("this Setid: " + uip["setid"] + ", Relation: " + uip["Relation"] + ", RelationshipType: " + uip["RelationshipType"] + ", Gender: " + uip["Gender"] + ", ControlType: " + uip["ControlType"] + ", Reference: " + uip["Reference"] + ", HotSpotRegionBedFile: " + uip["HotSpotRegionBedFile"] + ", TargetRegionBedFile: " + uip["TargetRegionBedFile"])

            theOtherDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in theOtherUip:
                theOtherDNA_RNA_Workflow = theOtherUip["DNA_RNA_Workflow"]
            thisDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in uip:
                thisDNA_RNA_Workflow = uip["DNA_RNA_Workflow"]
            theOtherNucleotideType = ""
            if "NucleotideType" in theOtherUip:
                theOtherNucleotideType = theOtherUip["NucleotideType"]
            thisNucleotideType = ""
            if "NucleotideType" in uip:
                thisNucleotideType = uip["NucleotideType"]
            # if the rows are for DNA_RNA workflow, then dont complain .. just pass it along..
            #debug print  uip["row"] +" == " + theOtherRowStr + " samplename similarity  " + uip["DNA_RNA_Workflow"] + " == "+ theOtherDNA_RNA_Workflow
            if (       ((uip["Workflow"]=="Upload Only") or (uip["Workflow"] == "")) and (thisNucleotideType != theOtherNucleotideType)     ):
                duplicateSamplesExists = False
            if (       (uip["setid"] == theOtherSetid) and (thisDNA_RNA_Workflow == theOtherDNA_RNA_Workflow ) and (thisDNA_RNA_Workflow == "DNA_RNA")      ):
                duplicateSamplesExists = False

            fieldValueDiffers = False
            if (uip["setid"] != theOtherSetid):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)      # TDB: Highlighting fields in these below conditions is not working, Check later.
            if (uip["Relation"] != theOtherRelation):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Relation", rowHighlightableFields)
            if (uip["RelationshipType"] != theOtherRelationShipType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
            if (uip["Gender"] != theOtherGender):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Gender", rowHighlightableFields)
            if (uip["ControlType"] != theOtherUipControlType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "ControlType", rowHighlightableFields)
            if (uip["Reference"] != theOtherUipReference):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Reference", rowHighlightableFields)
            if (uip["HotSpotRegionBedFile"] != theOtherUipHotSpotRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "HotSpotRegionBedFile", rowHighlightableFields)
            if (uip["TargetRegionBedFile"] != theOtherUipTargetRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "TargetRegionBedFile", rowHighlightableFields)

            if not fieldValueDiffers:
                duplicateSamplesExists = False


            if duplicateSamplesExists :
                msg ="Sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+theOtherRowStr+", Please change the sample name. Or, If you intend to use multi-barcodes per sample then please make sure all the other field values are same for all corresponding rows."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
                continue
            # else dont flag an error

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True
            if (  (isVariantCallerSelected != "Unknown")  and (isVariantCallerConfigured != "Unknown")  ):
                if (isVariantCallerSelected != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. Please select and configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue
                if (isVariantCallerConfigured != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. The Variant Caller plugin is selected, but not configured. Please configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
            continue
        # save the workflow information of the record on the setID.. also check workflow mismatch with previous row of the same setid
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[]
            setidHash[setid]["firstRecordRow"]=uip["row"]
            if uip["Workflow"] == "":
                setidHash[setid]["firstWorkflow"]=""
                setidHash[setid]["firstApplicationType"]=""
                setidHash[setid]["firstRelationshipType"]=""
                setidHash[setid]["firstRecordDNA_RNA"]=""
            else:
                setidHash[setid]["firstWorkflow"]=uip["Workflow"]
                setidHash[setid]["firstApplicationType"]=uip["ApplicationType"]
                setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
                setidHash[setid]["firstRecordDNA_RNA"]=uip["DNA_RNA_Workflow"]
            if "AllowMultipleRoleRecords" in uip :
                setidHash[setid]["firstAllowMultipleRoleRecords"]=uip["AllowMultipleRoleRecords"]
        else:
            if not bool(setidHash[setid]["firstRelationshipType"]):
                setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
            if not bool(setidHash[setid]["firstWorkflow"]):
                setidHash[setid]["firstWorkflow"]=uip["Workflow"]
            previousRow = setidHash[setid]["firstRecordRow"]
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            expectedRelationshipType = setidHash[setid]["firstRelationshipType"]
            expectedApplicationType = setidHash[setid]["firstApplicationType"]
            #print  uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
            if expectedWorkflow != uip["Workflow"]:
                msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
            elif expectedRelationshipType != uip["RelationshipType"]:
                #print  "error on " + uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
                msg="INTERNAL ERROR:  RelationshipType "+ uip["RelationshipType"] + " of the selected workflow, does not match a previous sample with the same SetID, with RelationshipType "+ expectedRelationshipType +" in row "+ previousRow+ "."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #elif expectedApplicationType != uip["ApplicationType"]:  #TBD add similar internal error
        setidHash[setid]["records"].append(uip)

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"] = uip["sample"]
        if uip["sample"] not in uniqueSamples:    # no need to repeat if the check has been done for the same sample name on an earlier row.
            sampleExistsCallResults = sampleExistsOnIR(inputJson)
            if sampleExistsCallResults.get("error") != "":
                if sampleExistsCallResults.get("status") == "true":
                    msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)

        # check all the generic rules for this uip .. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_5_12(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields)

        row = row + 1


    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the given set of records of the set
        rowsLooked = ""
        uniqueSamplesForThisSetID = []

        for record in setidHash[setid]["records"]:
            if record["sample"] not in uniqueSamplesForThisSetID:
                uniqueSamplesForThisSetID.append(record["sample"])
            

        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)
            # check if any extra roles exists.  Given that the above test exists for lack of roles, it is sufficient if we 
            # verify the total number of roles expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of roles required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            numRecordsForThisSetId = len(setidHash[setid]["records"])
            numOfUniqueSamples = len(uniqueSamplesForThisSetID)
            singleSampleApplicationTypeSet = set(["Amplicon Sequencing","Amplicon Low Frequency Sequencing","Low-Coverage Whole Genome Sequencing","Oncomine_RNA_Fusion","Annotation","Targeted Resequencing", \
                                                "AmpliSeqHD Single Pool","Low Frequency Resequencing","Mutational Load","ONCOLOGY_LIQUID_BIOPSY","ImmuneRepertoire","Genomic Resequencing"])
            if ( (setidHash[setid]["firstApplicationType"] in singleSampleApplicationTypeSet) and (numOfUniqueSamples > sizeOfRequiredRoles)) :
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of samples are found. Expected number of samples is " + str(sizeOfRequiredRoles) + ". "
                if   rowsLooked != "" :
                     if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                     else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Sample", rowHighlightableFields)  

            if (numRecordsForThisSetId > sizeOfRequiredRoles):
                complainAboutTooManyRoles = True

                uniqueRoles = []
                for uipInRecords in setidHash[setid]["records"]:
                    if (uipInRecords["Relation"] not in uniqueRoles):
                        uniqueRoles.append(uipInRecords["Relation"])
                if(len(uniqueRoles) == sizeOfRequiredRoles):
                    complainAboutTooManyRoles = False

                # ignore this check if the application type or other workflow settings already allws multi roles
                if "firstAllowMultipleRoleRecords" in setidHash[setid]:
                    if setidHash[setid]["firstAllowMultipleRoleRecords"] == "true":
                        complainAboutTooManyRoles = False
                # for DNA_RNA flag, its not the roles to be evaluated, its the nucleotideTypes to be evaluated.
                if setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA":
                    complainAboutTooManyRoles = False

                if complainAboutTooManyRoles:
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of RelationRoles is found. Expected number of roles is " + str(sizeOfRequiredRoles) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)

        ##
        # validate the nucleotidetypes, similar to the roles.
        # first check all the required nucleotides are there in the given set of records of the set
        #    Use the value of the rowsLooked,  populated from the above loop.
        if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")   ): 
            for validNucloetide in setidHash[setid]["validNucleotideTypes"]:
                foundNucleotide=0
                for record in setidHash[setid]["records"]:
                    if validNucloetide == record["NucleotideType"]:   #or NucleotideType
                        foundNucleotide = 1
                if foundNucleotide == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required NucleotideType "+ validNucloetide + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)
            # check if any extra nucleotides exists.  Given that the above test exists for missing nucleotides, it is sufficient if we 
            # verify the total number of nucleotides expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of nucleotides required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredNucleotides = len(setidHash[setid]["validNucleotideTypes"])
            numberOfUniqueSamples = len(uniqueSamplesForThisSetID)
            #numRecordsForThisSetId = len(setidHash[setid]["records"])   #already done as part of roles check
            if (numberOfUniqueSamples > sizeOfRequiredNucleotides):
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of Nucleotides is found. Expected number of Nucleotides is " + str(sizeOfRequiredNucleotides) + ". "
                if   rowsLooked != "" :
                    if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                    else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)


        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."





    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
           for e in  rowErrors[rowstr]:
              foundAtLeastOneError =1
              emsg = emsg + e + " ; "
        if rowstr in rowWarnings:
           for w in  rowWarnings[rowstr]:
              wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        if rowstr in rowHighlightableFields:
           k["highlightableFields"]=rowHighlightableFields[rowstr]
        else:
           k["highlightableFields"]=[]
        validationResults.append(k)

    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin


    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
           "conditions": conditions
           }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """

def validateAllRulesOnRecord_5_12(rules, uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                #msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                #inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                continue

            andForExists = 0
            if "AndFor" in rule:
                if rule["AndFor"]["Name"] not in uip:
                    continue
                else:
                    andForExists = 1

            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1
                    if valueCheck == 1 :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kValid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
                        # another small hardcoded update into the setidHash for later evaluation of the nucleotideType  uniqueness
                        if kValid == "NucleotideType":
                            if setid  in setidHash:
                                if "validNucleotideTypes" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validNucleotideTypes"] = vValid   # this is actually list of valid nucleotideTypes
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if valueCheck == 1 :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kInvalid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "NonEmpty" in rule:
                kFor=rule["For"]["Name"]
                vFor=rule["For"]["Value"]
                kNonEmpty=rule["NonEmpty"]["Name"]
                #print  "non empty validating   kfor " +kFor  + " vFor "+ vFor + "  kNonEmpty "+ kNonEmpty
                #if kFor not in uip :
                #    print  "kFor not in uip   "  + " kFor "+ kFor 
                #    continue
                if uip[kFor] == vFor :
                    if (   (kNonEmpty not in uip)   or  (uip[kNonEmpty] == "")   ):
                        #msg="Empty value found for " + kNonEmpty + " When "+ kFor + " is \"" + vFor +"\"."
                        msg="Empty value found for " + kNonEmpty
                        inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(row, kNonEmpty, rowHighlightableFields)
                        inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "Disabled" in rule:
                pass
            else:
                 msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                 inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

def validateUserInput_5_14(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]
    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"
    #variantCaller check variables
    requiresVariantCallerPlugin = False
    isVariantCallerSelected = "Unknown"
    if "isVariantCallerSelected" in userInput:
        isVariantCallerSelected = userInput["isVariantCallerSelected"]
    isVariantCallerConfigured = "Unknown"
    if "isVariantCallerConfigured" in userInput:
        isVariantCallerConfigured = userInput["isVariantCallerConfigured"]

    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    authCheckResult = authCheck(inputJson)
    #if authCheckResult.get("status") == "false":
    if (   (authCheckResult["status"] !="true")  or (authCheckResult["error"] != "none")   ):
        return {"status": "true",
                "error": "Authentication Failure",
                "validationResults": []}


    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []

    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
       currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
       orderedColumns[col["Order"]] = col

    # Get cancer types
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    # Extracting Gender column from the current rules for validation purpose. 
    validGenderList = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Gender"):
            validGenderList = col["Values"]

    # Extracting Relation column from the current rules for validation purpose.
    validRelations = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Relation"):
            validRelations = col["Values"]

    # getting the complete workflow list to extract the relationship type.
    allWorkflowListResult = getWorkflowList(inputJson)
    if (allWorkflowListResult["status"] != "true"):
        return allWorkflowListResult
    allWorkflowList = allWorkflowListResult["userWorkflows"]

    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """


    ###################################### This is a mock logic. This is not the real validation code. This is for test only
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
               resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    rowHighlightableFields={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]

    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
           uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets.  Also do the same for highlightableFields
        if  rowStr not in rowErrors:
           rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
           rowWarnings[rowStr]=[]
        if  rowStr not in rowHighlightableFields:
           rowHighlightableFields[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"] = uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"] = uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"] = uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if uip["Workflow"] !="":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                #uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
                #uip["DNA_RNA_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["DNA_RNA_Workflow"]
                #uip["OCP_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["OCP_Workflow"]
                if "RelationshipType" in currentlyAvaliableWorkflows[uip["Workflow"]]:
                    currentWorkflowDetails = currentlyAvaliableWorkflows[uip["Workflow"]]
                    if uip["RelationshipType"] and (currentWorkflowDetails["RelationshipType"] != uip["RelationshipType"]):
                        msg="selected relation "+ uip["RelationshipType"] + " is not valid." + rowStr
                        inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                        continue

                # another temporary check which is not required if all the parameters of workflow  were  properly handed off from TS
                if "RelationshipType" not in uip :
                    msg="INTERNAL ERROR:  For selected workflow "+ uip["Workflow"] + ", an internal key  RelationshipType is missing for row " + rowStr
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue

                #bring in all the workflow parameter so far available, into the uip hash.
                for k in  currentlyAvaliableWorkflows[uip["Workflow"]] :
                    uip[k] = currentlyAvaliableWorkflows[uip["Workflow"]][k]

                #Override cellularity percentage based on DNA RNA workflows
                if (uip["DNA_RNA_Workflow"] == "DNA_RNA"):
                    if (uip["nucleotideType"] == "DNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "1"
                    elif (uip["nucleotideType"] == "RNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "0"

                if ("tag_NO_CNV" in uip and uip["tag_NO_CNV"] == "true"):
                    uip["CELLULARITY_PCT_REQUIRED"] = "0"

                if ("tag_TAGSEQ" in uip and uip["tag_TAGSEQ"] == "true"):
                    uip["CELLULARITY_PCT_REQUIRED"] = "0"

            else:
                uip["ApplicationType"] = "unknown"
                msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time" + rowStr
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                continue
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""
        if  "cellularityPct" in uip :
            uip["CellularityPct"] = uip["cellularityPct"]
        if  "CellularityPct" not in uip :
            uip["CellularityPct"] = ""
        if  "cancerType" in uip :
            uip["CancerType"] = uip["cancerType"]
        if  "CancerType" not in uip :
            uip["CancerType"] = ""
        if  "controlType" in uip :
            if uip["controlType"] == "None":
                uip["ControlType"] = ""
            else:
                uip["ControlType"] = uip["controlType"]
        if  "controlType" not in uip :
            uip["ControlType"] = ""
        if  "reference" in uip :
            uip["Reference"] = uip["reference"]
        if  "reference" not in uip :
            uip["Reference"] = ""
        if  "hotSpotRegionBedFile" in uip :
            uip["HotSpotRegionBedFile"] = uip["hotSpotRegionBedFile"]
        if  "hotSpotRegionBedFile" not in uip :
            uip["HotSpotRegionBedFile"] = ""
        if  "targetRegionBedFile" in uip :
            uip["TargetRegionBedFile"] = uip["targetRegionBedFile"]
        if  "targetRegionBedFile" not in uip :
            uip["TargetRegionBedFile"] = ""
            

        if(uip["CancerType"] and (uip["CancerType"] not in cancerTypesList)):
            msg="selected cancer type "+ uip["CancerType"] + " is not valid for this IR user account. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["Gender"] and (uip["Gender"] not in validGenderList)):
            msg="selected gender type "+ uip["Gender"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["RelationRole"] and (uip["RelationRole"] not in validRelations)):
            msg="selected relation role "+ uip["RelationRole"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            continue

        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = uip  #later if its a three level then make it into an array of uips
        else:
            duplicateSamplesExists = True
            theOtherUip = uniqueSamples[uip["sample"]]
            theOtherRowStr = theOtherUip["row"]
            theOtherSetid = theOtherUip["setid"]
            theOtherRelation = theOtherUip["Relation"]
            theOtherRelationShipType = theOtherUip["RelationshipType"]
            theOtherGender = theOtherUip["Gender"]
            if  "controlType" in theOtherUip :
                if theOtherUip["controlType"] == "None":
                    theOtherUipControlType = ""
                else:
                    theOtherUipControlType = theOtherUip["controlType"]
            if  "controlType" not in theOtherUip :
                theOtherUipControlType = ""
            if  "reference" in theOtherUip :
                theOtherUipReference = theOtherUip["reference"]
            if  "reference" not in theOtherUip :
                theOtherUipReference = ""
            if  "hotSpotRegionBedFile" in theOtherUip :
                theOtherUipHotSpotRegionBedFile = theOtherUip["hotSpotRegionBedFile"]
            if  "hotSpotRegionBedFile" not in theOtherUip :
                theOtherUipHotSpotRegionBedFile = ""
            if  "targetRegionBedFile" in theOtherUip :
                theOtherUipTargetRegionBedFile = theOtherUip["targetRegionBedFile"]
            if  "targetRegionBedFile" not in theOtherUip :
                theOtherUipTargetRegionBedFile = ""

            write_debug_log("OtherSetid: " + theOtherSetid + ", theOtherRelation: " + theOtherRelation + ", theOtherRelationShipType: " + theOtherRelationShipType + ", theOtherGender: " + theOtherGender + ", theOtherControlType: " + theOtherUipControlType + ", theOtherUipReference: " + theOtherUipReference + ", theOtherUipHotSpotRegionBedFile: " + theOtherUipHotSpotRegionBedFile + ", theOtherUipTargetRegionBedFile: " + theOtherUipTargetRegionBedFile)
            write_debug_log("this Setid: " + uip["setid"] + ", Relation: " + uip["Relation"] + ", RelationshipType: " + uip["RelationshipType"] + ", Gender: " + uip["Gender"] + ", ControlType: " + uip["ControlType"] + ", Reference: " + uip["Reference"] + ", HotSpotRegionBedFile: " + uip["HotSpotRegionBedFile"] + ", TargetRegionBedFile: " + uip["TargetRegionBedFile"])

            theOtherDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in theOtherUip:
                theOtherDNA_RNA_Workflow = theOtherUip["DNA_RNA_Workflow"]
            thisDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in uip:
                thisDNA_RNA_Workflow = uip["DNA_RNA_Workflow"]
            theOtherNucleotideType = ""
            if "NucleotideType" in theOtherUip:
                theOtherNucleotideType = theOtherUip["NucleotideType"]
            thisNucleotideType = ""
            if "NucleotideType" in uip:
                thisNucleotideType = uip["NucleotideType"]
            # if the rows are for DNA_RNA workflow, then dont complain .. just pass it along..
            #debug print  uip["row"] +" == " + theOtherRowStr + " samplename similarity  " + uip["DNA_RNA_Workflow"] + " == "+ theOtherDNA_RNA_Workflow
            if (       ((uip["Workflow"]=="Upload Only") or (uip["Workflow"] == "")) and (thisNucleotideType != theOtherNucleotideType)     ):
                duplicateSamplesExists = False
            if (       (uip["setid"] == theOtherSetid) and (thisDNA_RNA_Workflow == theOtherDNA_RNA_Workflow ) and (thisDNA_RNA_Workflow == "DNA_RNA")      ):
                duplicateSamplesExists = False

            fieldValueDiffers = False
            if (uip["setid"] != theOtherSetid):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)      # TDB: Highlighting fields in these below conditions is not working, Check later.
            if (uip["Relation"] != theOtherRelation):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Relation", rowHighlightableFields)
            if (uip["RelationshipType"] != theOtherRelationShipType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
            if (uip["Gender"] != theOtherGender):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Gender", rowHighlightableFields)
            if (uip["ControlType"] != theOtherUipControlType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "ControlType", rowHighlightableFields)
            if (uip["Reference"] != theOtherUipReference):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Reference", rowHighlightableFields)
            if (uip["HotSpotRegionBedFile"] != theOtherUipHotSpotRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "HotSpotRegionBedFile", rowHighlightableFields)
            if (uip["TargetRegionBedFile"] != theOtherUipTargetRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "TargetRegionBedFile", rowHighlightableFields)

            if not fieldValueDiffers:
                duplicateSamplesExists = False


            if duplicateSamplesExists :
                msg ="Sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+theOtherRowStr+", Please change the sample name. Or, If you intend to use multi-barcodes per sample then please make sure all the other field values are same for all corresponding rows."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
                continue
            # else dont flag an error

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True
            if (  (isVariantCallerSelected != "Unknown")  and (isVariantCallerConfigured != "Unknown")  ):
                if (isVariantCallerSelected != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. Please select and configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue
                if (isVariantCallerConfigured != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. The Variant Caller plugin is selected, but not configured. Please configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
            continue
        # save the workflow information of the record on the setID.. also check workflow mismatch with previous row of the same setid
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[]
            setidHash[setid]["firstRecordRow"]=uip["row"]
            if uip["Workflow"] == "":
                setidHash[setid]["firstWorkflow"]=""
                setidHash[setid]["firstApplicationType"]=""
                setidHash[setid]["firstRelationshipType"]=""
                setidHash[setid]["firstRecordDNA_RNA"]=""
            else:
                setidHash[setid]["firstWorkflow"]=uip["Workflow"]
                setidHash[setid]["firstApplicationType"]=uip["ApplicationType"]
                setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
                setidHash[setid]["firstRecordDNA_RNA"]=uip["DNA_RNA_Workflow"]
            if "AllowMultipleRoleRecords" in uip :
                setidHash[setid]["firstAllowMultipleRoleRecords"]=uip["AllowMultipleRoleRecords"]
        else:
            if not bool(setidHash[setid]["firstRelationshipType"]):
                setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
            if not bool(setidHash[setid]["firstWorkflow"]):
                setidHash[setid]["firstWorkflow"]=uip["Workflow"]
            previousRow = setidHash[setid]["firstRecordRow"]
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            expectedRelationshipType = setidHash[setid]["firstRelationshipType"]
            expectedApplicationType = setidHash[setid]["firstApplicationType"]
            #print  uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
            if expectedWorkflow != uip["Workflow"]:
                msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
            elif expectedRelationshipType != uip["RelationshipType"]:
                #print  "error on " + uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
                msg="INTERNAL ERROR:  RelationshipType "+ uip["RelationshipType"] + " of the selected workflow, does not match a previous sample with the same SetID, with RelationshipType "+ expectedRelationshipType +" in row "+ previousRow+ "."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #elif expectedApplicationType != uip["ApplicationType"]:  #TBD add similar internal error
        setidHash[setid]["records"].append(uip)

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"] = uip["sample"]
        if uip["sample"] not in uniqueSamples:    # no need to repeat if the check has been done for the same sample name on an earlier row.
            sampleExistsCallResults = sampleExistsOnIR(inputJson)
            if sampleExistsCallResults.get("error") != "":
                if sampleExistsCallResults.get("status") == "true":
                    msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)

        # check all the generic rules for this uip .. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_5_14(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields)

        row = row + 1


    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the given set of records of the set
        rowsLooked = ""
        uniqueSamplesForThisSetID = []

        for record in setidHash[setid]["records"]:
            if record["sample"] not in uniqueSamplesForThisSetID:
                uniqueSamplesForThisSetID.append(record["sample"])
            

        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)
            # check if any extra roles exists.  Given that the above test exists for lack of roles, it is sufficient if we 
            # verify the total number of roles expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of roles required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            numRecordsForThisSetId = len(setidHash[setid]["records"])
            numOfUniqueSamples = len(uniqueSamplesForThisSetID)
            singleSampleApplicationTypeSet = set(["Amplicon Sequencing","Amplicon Low Frequency Sequencing","Low-Coverage Whole Genome Sequencing","Oncomine_RNA_Fusion","Annotation","Targeted Resequencing", \
                                                "AmpliSeqHD Single Pool","Low Frequency Resequencing","Mutational Load","ONCOLOGY_LIQUID_BIOPSY","ImmuneRepertoire","Genomic Resequencing"])
            if ( (setidHash[setid]["firstApplicationType"] in singleSampleApplicationTypeSet) and (numOfUniqueSamples > sizeOfRequiredRoles)) :
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of samples are found. Expected number of samples is " + str(sizeOfRequiredRoles) + ". "
                if   rowsLooked != "" :
                     if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                     else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Sample", rowHighlightableFields)  

            if (numRecordsForThisSetId > sizeOfRequiredRoles):
                complainAboutTooManyRoles = True

                uniqueRoles = []
                for uipInRecords in setidHash[setid]["records"]:
                    if (uipInRecords["Relation"] not in uniqueRoles):
                        uniqueRoles.append(uipInRecords["Relation"])
                if(len(uniqueRoles) == sizeOfRequiredRoles):
                    complainAboutTooManyRoles = False

                # ignore this check if the application type or other workflow settings already allws multi roles
                if "firstAllowMultipleRoleRecords" in setidHash[setid]:
                    if setidHash[setid]["firstAllowMultipleRoleRecords"] == "true":
                        complainAboutTooManyRoles = False
                # for DNA_RNA flag, its not the roles to be evaluated, its the nucleotideTypes to be evaluated.
                if setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA":
                    complainAboutTooManyRoles = False

                if complainAboutTooManyRoles:
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of RelationRoles is found. Expected number of roles is " + str(sizeOfRequiredRoles) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)

        ##
        # validate the nucleotidetypes, similar to the roles.
        # first check all the required nucleotides are there in the given set of records of the set
        #    Use the value of the rowsLooked,  populated from the above loop.
        if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")   ): 
            for validNucloetide in setidHash[setid]["validNucleotideTypes"]:
                foundNucleotide=0
                for record in setidHash[setid]["records"]:
                    if validNucloetide == record["NucleotideType"]:   #or NucleotideType
                        foundNucleotide = 1
                if foundNucleotide == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required NucleotideType "+ validNucloetide + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)
            # check if any extra nucleotides exists.  Given that the above test exists for missing nucleotides, it is sufficient if we 
            # verify the total number of nucleotides expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of nucleotides required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredNucleotides = len(setidHash[setid]["validNucleotideTypes"])
            numberOfUniqueSamples = len(uniqueSamplesForThisSetID)
            #numRecordsForThisSetId = len(setidHash[setid]["records"])   #already done as part of roles check
            if (numberOfUniqueSamples > sizeOfRequiredNucleotides):
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of Nucleotides is found. Expected number of Nucleotides is " + str(sizeOfRequiredNucleotides) + ". "
                if   rowsLooked != "" :
                    if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                    else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)


        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."





    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
           for e in  rowErrors[rowstr]:
              foundAtLeastOneError =1
              emsg = emsg + e + " ; "
        if rowstr in rowWarnings:
           for w in  rowWarnings[rowstr]:
              wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        if rowstr in rowHighlightableFields:
           k["highlightableFields"]=rowHighlightableFields[rowstr]
        else:
           k["highlightableFields"]=[]
        validationResults.append(k)

    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin


    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
           "conditions": conditions
           }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """

def validateAllRulesOnRecord_5_14(rules, uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                #msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                #inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                continue

            andForExists = 0
            if "AndFor" in rule:
                if rule["AndFor"]["Name"] not in uip:
                    continue
                else:
                    andForExists = 1

            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1
                    if valueCheck == 1 :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kValid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
                        # another small hardcoded update into the setidHash for later evaluation of the nucleotideType  uniqueness
                        if kValid == "NucleotideType":
                            if setid  in setidHash:
                                if "validNucleotideTypes" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validNucleotideTypes"] = vValid   # this is actually list of valid nucleotideTypes
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if valueCheck == 1 :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid
                            inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kInvalid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "NonEmpty" in rule:
                kFor=rule["For"]["Name"]
                vFor=rule["For"]["Value"]
                kNonEmpty=rule["NonEmpty"]["Name"]
                #print  "non empty validating   kfor " +kFor  + " vFor "+ vFor + "  kNonEmpty "+ kNonEmpty
                #if kFor not in uip :
                #    print  "kFor not in uip   "  + " kFor "+ kFor 
                #    continue
                if uip[kFor] == vFor :
                    if (   (kNonEmpty not in uip)   or  (uip[kNonEmpty] == "")   ):
                        #msg="Empty value found for " + kNonEmpty + " When "+ kFor + " is \"" + vFor +"\"."
                        msg="Empty value found for " + kNonEmpty
                        inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(row, kNonEmpty, rowHighlightableFields)
                        inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "Disabled" in rule:
                pass
            else:
                 msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                 inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

def validateUserInput_5_16(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"

    #variantCaller check variables
    requiresVariantCallerPlugin = False
    isVariantCallerSelected = "Unknown"
    if "isVariantCallerSelected" in userInput:
        isVariantCallerSelected = userInput["isVariantCallerSelected"]
    isVariantCallerConfigured = "Unknown"
    if "isVariantCallerConfigured" in userInput:
        isVariantCallerConfigured = userInput["isVariantCallerConfigured"]

    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    authCheckResult = authCheck(inputJson)
    #if authCheckResult.get("status") == "false":
    if (   (authCheckResult["status"] !="true")  or (authCheckResult["error"] != "none")   ):
        return {"status": "true",
                "error": "Authentication Failure",
                "validationResults": []}

    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []

    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
        currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
        orderedColumns[col["Order"]] = col

    # Get cancer types
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    # Extracting Gender column from the current rules for validation purpose.
    validGenderList = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Gender"):
            validGenderList = col["Values"]

    # Extracting Relation column from the current rules for validation purpose.
    validRelations = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Relation"):
            validRelations = col["Values"]

    # getting the complete workflow list to extract the relationship type.
    allWorkflowListResult = getWorkflowList(inputJson)
    if (allWorkflowListResult["status"] != "true"):
        return allWorkflowListResult
    allWorkflowList = allWorkflowListResult["userWorkflows"]

    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """


    ###################################### This is a mock logic. This is not the real validation code. This is for test only
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
                resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    rowHighlightableFields={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]
    similar_sample_name_check_for_wf={}
    immune_rep_multi_wf=[]
    unique_sample_workflow_list = []
    unique_sample_wf_dict={}
    duplicate_sample_exists = False
    isImmuneRep = False

    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
            uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets.  Also do the same for highlightableFields
        if  rowStr not in rowErrors:
            rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
            rowWarnings[rowStr]=[]
        if  rowStr not in rowHighlightableFields:
            rowHighlightableFields[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"] = uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"] = uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"] = uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if uip["Workflow"] !="":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                #uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
                #uip["DNA_RNA_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["DNA_RNA_Workflow"]
                #uip["OCP_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["OCP_Workflow"]
                if "RelationshipType" in currentlyAvaliableWorkflows[uip["Workflow"]]:
                    currentWorkflowDetails = currentlyAvaliableWorkflows[uip["Workflow"]]
                    if uip["RelationshipType"] and (currentWorkflowDetails["RelationshipType"] != uip["RelationshipType"]):
                        msg="selected relation "+ uip["RelationshipType"] + " is not valid." + rowStr
                        inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                        continue

                # another temporary check which is not required if all the parameters of workflow  were  properly handed off from TS
                if "RelationshipType" not in uip :
                    msg="INTERNAL ERROR:  For selected workflow "+ uip["Workflow"] + ", an internal key  RelationshipType is missing for row " + rowStr
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue

                #bring in all the workflow parameter so far available, into the uip hash.
                for k in  currentlyAvaliableWorkflows[uip["Workflow"]] :
                    uip[k] = currentlyAvaliableWorkflows[uip["Workflow"]][k]

                #Override cellularity percentage based on DNA RNA workflows
                if (uip["DNA_RNA_Workflow"] == "DNA_RNA"):
                    if (uip["nucleotideType"] == "DNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "1"
                    elif (uip["nucleotideType"] == "RNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "0"

                if ("tag_NO_CNV" in uip and uip["tag_NO_CNV"] == "true"):
                    uip["CELLULARITY_PCT_REQUIRED"] = "0"

                if ("tag_TAGSEQ" in uip and uip["tag_TAGSEQ"] == "true"):
                    uip["CELLULARITY_PCT_REQUIRED"] = "0"

            else:
                uip["ApplicationType"] = "unknown"
                msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time" + rowStr
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                continue
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""
        if  "cellularityPct" in uip :
            uip["CellularityPct"] = uip["cellularityPct"]
        if  "CellularityPct" not in uip :
            uip["CellularityPct"] = ""
        if  "cancerType" in uip :
            uip["CancerType"] = uip["cancerType"]
        if  "CancerType" not in uip :
            uip["CancerType"] = ""
        if  "controlType" in uip :
            if uip["controlType"] == "None":
                uip["ControlType"] = ""
            else:
                uip["ControlType"] = uip["controlType"]
        if  "controlType" not in uip :
            uip["ControlType"] = ""
        if  "reference" in uip :
            uip["Reference"] = uip["reference"]
        if  "reference" not in uip :
            uip["Reference"] = ""
        if  "hotSpotRegionBedFile" in uip :
            uip["HotSpotRegionBedFile"] = uip["hotSpotRegionBedFile"]
        if  "hotSpotRegionBedFile" not in uip :
            uip["HotSpotRegionBedFile"] = ""
        if  "targetRegionBedFile" in uip :
            uip["TargetRegionBedFile"] = uip["targetRegionBedFile"]
        if  "targetRegionBedFile" not in uip :
            uip["TargetRegionBedFile"] = ""


        if(uip["CancerType"] and (uip["CancerType"] not in cancerTypesList)):
            msg="selected cancer type "+ uip["CancerType"] + " is not valid for this IR user account. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["Gender"] and (uip["Gender"] not in validGenderList)):
            msg="selected gender type "+ uip["Gender"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["RelationRole"] and (uip["RelationRole"] not in validRelations)):
            msg="selected relation role "+ uip["RelationRole"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            continue

        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = uip  #later if its a three level then make it into an array of uips
            unique_sample_row_no = uniqueSamples[uip["sample"]]["row"]
            for rec in userInputInfo:
                if rec["row"] == unique_sample_row_no:
                    unique_sample_workflow_list.append(rec["Workflow"])
            unique_sample_wf_dict[unique_sample_row_no] = unique_sample_workflow_list
            unique_sample_wf_dict["SetID"] = uip["SetID"]
            unique_sample_wf_dict["sample"] = uip["sample"]
            unique_sample_wf_dict["row"] = uip["row"]
            write_debug_log(unique_sample_wf_dict)
        else:
            duplicateSamplesExists = True
            theOtherUip = uniqueSamples[uip["sample"]]
            theOtherRowStr = theOtherUip["row"]
            theOtherSetid = theOtherUip["setid"]
            theOtherRelation = theOtherUip["Relation"]
            theOtherRelationShipType = theOtherUip["RelationshipType"]
            theOtherGender = theOtherUip["Gender"]
            if  "controlType" in theOtherUip :
                if theOtherUip["controlType"] == "None":
                    theOtherUipControlType = ""
                else:
                    theOtherUipControlType = theOtherUip["controlType"]
            if  "controlType" not in theOtherUip :
                theOtherUipControlType = ""
            if  "reference" in theOtherUip :
                theOtherUipReference = theOtherUip["reference"]
            if  "reference" not in theOtherUip :
                theOtherUipReference = ""
            if  "hotSpotRegionBedFile" in theOtherUip :
                theOtherUipHotSpotRegionBedFile = theOtherUip["hotSpotRegionBedFile"]
            if  "hotSpotRegionBedFile" not in theOtherUip :
                theOtherUipHotSpotRegionBedFile = ""
            if  "targetRegionBedFile" in theOtherUip :
                theOtherUipTargetRegionBedFile = theOtherUip["targetRegionBedFile"]
            if  "targetRegionBedFile" not in theOtherUip :
                theOtherUipTargetRegionBedFile = ""

            write_debug_log("OtherSetid: " + theOtherSetid + ", theOtherRelation: " + theOtherRelation + ", theOtherRelationShipType: " + theOtherRelationShipType + ", theOtherGender: " + theOtherGender + ", theOtherControlType: " + theOtherUipControlType + ", theOtherUipReference: " + theOtherUipReference + ", theOtherUipHotSpotRegionBedFile: " + theOtherUipHotSpotRegionBedFile + ", theOtherUipTargetRegionBedFile: " + theOtherUipTargetRegionBedFile)
            write_debug_log("this Setid: " + uip["setid"] + ", Relation: " + uip["Relation"] + ", RelationshipType: " + uip["RelationshipType"] + ", Gender: " + uip["Gender"] + ", ControlType: " + uip["ControlType"] + ", Reference: " + uip["Reference"] + ", HotSpotRegionBedFile: " + uip["HotSpotRegionBedFile"] + ", TargetRegionBedFile: " + uip["TargetRegionBedFile"])

            theOtherDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in theOtherUip:
                theOtherDNA_RNA_Workflow = theOtherUip["DNA_RNA_Workflow"]
            thisDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in uip:
                thisDNA_RNA_Workflow = uip["DNA_RNA_Workflow"]
            theOtherNucleotideType = ""
            if "NucleotideType" in theOtherUip:
                theOtherNucleotideType = theOtherUip["NucleotideType"]
            thisNucleotideType = ""
            if "NucleotideType" in uip:
                thisNucleotideType = uip["NucleotideType"]
            # if the rows are for DNA_RNA workflow, then dont complain .. just pass it along..
            #debug print  uip["row"] +" == " + theOtherRowStr + " samplename similarity  " + uip["DNA_RNA_Workflow"] + " == "+ theOtherDNA_RNA_Workflow
            if (       ((uip["Workflow"]=="Upload Only") or (uip["Workflow"] == "")) and (thisNucleotideType != theOtherNucleotideType)     ):
                duplicateSamplesExists = False
            if (       (uip["setid"] == theOtherSetid) and (thisDNA_RNA_Workflow == theOtherDNA_RNA_Workflow ) and (thisDNA_RNA_Workflow == "DNA_RNA")      ):
                duplicateSamplesExists = False

            fieldValueDiffers = False
            if (uip["setid"] != theOtherSetid):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)      # TDB: Highlighting fields in these below conditions is not working, Check later.
            if (uip["Relation"] != theOtherRelation):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Relation", rowHighlightableFields)
            if (uip["RelationshipType"] != theOtherRelationShipType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
            if (uip["Gender"] != theOtherGender):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Gender", rowHighlightableFields)
            if (uip["ControlType"] != theOtherUipControlType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "ControlType", rowHighlightableFields)
            if (uip["Reference"] != theOtherUipReference):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Reference", rowHighlightableFields)
            if (uip["HotSpotRegionBedFile"] != theOtherUipHotSpotRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "HotSpotRegionBedFile", rowHighlightableFields)
            if (uip["TargetRegionBedFile"] != theOtherUipTargetRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "TargetRegionBedFile", rowHighlightableFields)
            if not unique_sample_wf_dict.has_key(str(uip["row"])):
                immune_rep_multi_wf.append(uip["Workflow"])
                similar_sample_name_check_for_wf[uip["row"]] = immune_rep_multi_wf
                similar_sample_name_check_for_wf["SetID"] = uip["SetID"]
                similar_sample_name_check_for_wf["sample"] = uip["sample"]
                similar_sample_name_check_for_wf["row"] = uip["row"]
                write_debug_log(similar_sample_name_check_for_wf)
                duplicate_sample_exists = True



            if not fieldValueDiffers:
                duplicateSamplesExists = False


            if duplicateSamplesExists :
                msg ="Sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+theOtherRowStr+", Please change the sample name. Or, If you intend to use multi-barcodes per sample then please make sure all the other field values are same for all corresponding rows."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
                continue
            # else dont flag an error

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True
            if (  (isVariantCallerSelected != "Unknown")  and (isVariantCallerConfigured != "Unknown")  ):
                if (isVariantCallerSelected != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. Please select and configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue
                if (isVariantCallerConfigured != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. The Variant Caller plugin is selected, but not configured. Please configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
            continue
        # save the workflow information of the record on the setID.. also check workflow mismatch with previous row of the same setid
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[]
            setidHash[setid]["firstRecordRow"]=uip["row"]
            if uip["Workflow"] == "":
                setidHash[setid]["firstWorkflow"]=""
                setidHash[setid]["firstApplicationType"]=""
                setidHash[setid]["firstRelationshipType"]=""
                setidHash[setid]["firstRecordDNA_RNA"]=""
            else:
                setidHash[setid]["firstWorkflow"]=uip["Workflow"]
                setidHash[setid]["firstApplicationType"]=uip["ApplicationType"]
                setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
                setidHash[setid]["firstRecordDNA_RNA"]=uip["DNA_RNA_Workflow"]
            if "AllowMultipleRoleRecords" in uip :
                setidHash[setid]["firstAllowMultipleRoleRecords"]=uip["AllowMultipleRoleRecords"]
        else:
            if not bool(setidHash[setid]["firstRelationshipType"]):
                setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
            if not bool(setidHash[setid]["firstWorkflow"]):
                setidHash[setid]["firstWorkflow"]=uip["Workflow"]
            previousRow = setidHash[setid]["firstRecordRow"]
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            expectedRelationshipType = setidHash[setid]["firstRelationshipType"]
            expectedApplicationType = setidHash[setid]["firstApplicationType"]
            #print  uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType

            if expectedWorkflow != uip["Workflow"]:
                isValidationAllowed = isMultiWorkflowSelectionEnabled(uip["ApplicationType"])
                if not bool(isValidationAllowed):
                    msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
            elif expectedRelationshipType != uip["RelationshipType"]:
                #print  "error on " + uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
                msg="INTERNAL ERROR:  RelationshipType "+ uip["RelationshipType"] + " of the selected workflow, does not match a previous sample with the same SetID, with RelationshipType "+ expectedRelationshipType +" in row "+ previousRow+ "."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #elif expectedApplicationType != uip["ApplicationType"]:  #TBD add similar internal error
        setidHash[setid]["records"].append(uip)

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"] = uip["sample"]
        if uip["sample"] not in uniqueSamples:    # no need to repeat if the check has been done for the same sample name on an earlier row.
            sampleExistsCallResults = sampleExistsOnIR(inputJson)
            if sampleExistsCallResults.get("error") != "":
                if sampleExistsCallResults.get("status") == "true":
                    msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)

        # check all the generic rules for this uip .. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_5_16(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields)
        if row == 1:
            if "firstApplicationType" in setidHash[setid]:
                if (setidHash[setid]["firstApplicationType"] == "ImmuneRepertoire") :
                    isImmuneRep = True

        row = row + 1


    if duplicate_sample_exists:
        if similar_sample_name_check_for_wf["SetID"] == unique_sample_wf_dict["SetID"]:
            if similar_sample_name_check_for_wf["sample"] == unique_sample_wf_dict["sample"]:
                sample_wf_list1=[]
                sample_wf_list2=[]
                for k,v in similar_sample_name_check_for_wf.items():
                    if type(similar_sample_name_check_for_wf[k]) == list:
                        sample_wf_list1.append(similar_sample_name_check_for_wf[k])
                for k,v in unique_sample_wf_dict.items():
                    if type(unique_sample_wf_dict[k]) == list:
                        sample_wf_list2.append(unique_sample_wf_dict[k])
                result1_list = sample_wf_list1[0]
                result2_list = sample_wf_list2[0]
                write_debug_log(result1_list)
                write_debug_log(result2_list)
                for items in result1_list:
                    if items not in result2_list:
                        msg ="Sample name "+similar_sample_name_check_for_wf["sample"] + " in row "+ similar_sample_name_check_for_wf["row"]+" is also in row "+unique_sample_wf_dict["row"]+", Please change the sample name. Or, If you intend to use multi-barcodes per sample then please make sure similar workflows are selected in corresponding rows."
                        inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)

    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the given set of records of the set
        rowsLooked = ""
        uniqueSamplesForThisSetID = []

        for record in setidHash[setid]["records"]:
            if record["sample"] not in uniqueSamplesForThisSetID:
                uniqueSamplesForThisSetID.append(record["sample"])


        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)
            # check if any extra roles exists.  Given that the above test exists for lack of roles, it is sufficient if we
            # verify the total number of roles expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of roles required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            numRecordsForThisSetId = len(setidHash[setid]["records"])
            numOfUniqueSamples = len(uniqueSamplesForThisSetID)
            singleSampleApplicationTypeSet = set(["Amplicon Sequencing","Amplicon Low Frequency Sequencing","Low-Coverage Whole Genome Sequencing","Oncomine_RNA_Fusion","Annotation","Targeted Resequencing", \
                                                  "AmpliSeqHD Single Pool","Low Frequency Resequencing","Mutational Load","ONCOLOGY_LIQUID_BIOPSY","ImmuneRepertoire","Genomic Resequencing"])
            if ( (setidHash[setid]["firstApplicationType"] in singleSampleApplicationTypeSet) and (numOfUniqueSamples > sizeOfRequiredRoles)) :
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of samples are found. Expected number of samples is " + str(sizeOfRequiredRoles) + ". "
                if   rowsLooked != "" :
                    if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                    else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Sample", rowHighlightableFields)

            if (numRecordsForThisSetId > sizeOfRequiredRoles):
                complainAboutTooManyRoles = True

                uniqueRoles = []
                for uipInRecords in setidHash[setid]["records"]:
                    if (uipInRecords["Relation"] not in uniqueRoles):
                        uniqueRoles.append(uipInRecords["Relation"])
                if(len(uniqueRoles) == sizeOfRequiredRoles):
                    complainAboutTooManyRoles = False

                # ignore this check if the application type or other workflow settings already allws multi roles
                if "firstAllowMultipleRoleRecords" in setidHash[setid]:
                    if setidHash[setid]["firstAllowMultipleRoleRecords"] == "true":
                        complainAboutTooManyRoles = False
                # for DNA_RNA flag, its not the roles to be evaluated, its the nucleotideTypes to be evaluated.
                if setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA":
                    complainAboutTooManyRoles = False

                if complainAboutTooManyRoles:
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of RelationRoles is found. Expected number of roles is " + str(sizeOfRequiredRoles) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)

        ##
        # validate the nucleotidetypes, similar to the roles.
        # first check all the required nucleotides are there in the given set of records of the set
        #    Use the value of the rowsLooked,  populated from the above loop.
        if ( isImmuneRep == True ):
            if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "DNA") ):
                # for validNucloetide in setidHash[setid]["validNucleotideTypes"]:
                #     foundNucleotide=0
                for record in setidHash[setid]["records"]:
                    foundNucleotide = 0
                    if (record["DNA_RNA_Workflow"] == record["NucleotideType"]):   #or NucleotideType
                        foundNucleotide = 1
                    if foundNucleotide == 0 :
                        msg="For workflow " + record["Workflow"] +", a required NucleotideType "+ record["NucleotideType"] + " is not found. "
                        # AS per demo comments removing this code.
                        #                     if   rowsLooked != "" :
                        #                         if rowsLooked.find(",") != -1  :
                        #                             msg = msg + "Please check the rows " + rowsLooked
                        #                         else:
                        #                             msg = msg + "Please check the row " + rowsLooked
                        inputValidationErrorHandle(record["row"], "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                        inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)
                # check if any extra nucleotides exists.  Given that the above test exists for missing nucleotides, it is sufficient if we
                # verify the total number of nucleotides expected and number of records got, for this setid. If there is a mismatch,
                # it means there are more than the number of nucleotides required.
                #    Use the value of the rowsLooked,  populated from the above loop.
                sizeOfRequiredNucleotides = len(setidHash[setid]["validNucleotideTypes"])
                numberOfUniqueSamples = len(uniqueSamplesForThisSetID)
                #numRecordsForThisSetId = len(setidHash[setid]["records"])   #already done as part of roles check
                if (numberOfUniqueSamples > sizeOfRequiredNucleotides):
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of Nucleotides is found. Expected number of Nucleotides is " + str(sizeOfRequiredNucleotides) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)
        else:
            if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "DNA") ):
                for validNucleotide in setidHash[setid]["validNucleotideTypes"]:
                    foundNucleotide=0
                    for record in setidHash[setid]["records"]:
                        if validNucleotide == record["NucleotideType"]:   #or NucleotideType
                            foundNucleotide = 1

                    if foundNucleotide == 0 :
                        msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required NucleotideType "+ validNucleotide + " is not found. "
                        if   rowsLooked != "" :
                            if rowsLooked.find(",") != -1  :
                                msg = msg + "Please check the rows " + rowsLooked
                            else:
                                msg = msg + "Please check the row " + rowsLooked
                        inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                        inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)

        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."

    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    message=""
    valid = "false"
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
            for e in  rowErrors[rowstr]:
                foundAtLeastOneError =1
                if (message.find(e) == -1):
		    emsg = emsg + e + " ; "
		    message = message + e
                    valid = "true"
        if rowstr in rowWarnings:
            for w in  rowWarnings[rowstr]:
                wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        if rowstr in rowHighlightableFields:
            k["highlightableFields"]=rowHighlightableFields[rowstr]
        else:
            k["highlightableFields"]=[]
	if (valid == "true"):
            if not validationResults:
                validationResults.append(k)
            else:
                for index, error_result in enumerate(validationResults):
                    k["errorMessage"] = ""
                    if k["errors"] != error_result["errors"]:
                        validationResults.append(k)
                        validationResults=  [item for index, item in enumerate(validationResults) if item not in validationResults[index + 1:]]




    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin


    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
            "conditions": conditions
            }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """

def validateUserInput_5_18(inputJson):
    userInput = inputJson["userInput"]
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"

    #variantCaller check variables
    requiresVariantCallerPlugin = False
    isVariantCallerSelected = "Unknown"
    if "isVariantCallerSelected" in userInput:
        isVariantCallerSelected = userInput["isVariantCallerSelected"]
    isVariantCallerConfigured = "Unknown"
    if "isVariantCallerConfigured" in userInput:
        isVariantCallerConfigured = userInput["isVariantCallerConfigured"]

    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "true",
                "error": "UserInput Validation Query not supported for this version of IR " + version,
                "validationResults": []}

    authCheckResult = authCheck(inputJson)
    #if authCheckResult.get("status") == "false":
    if (   (authCheckResult["status"] !="true")  or (authCheckResult["error"] != "none")   ):
        return {"status": "true",
                "error": "Authentication Failure",
                "validationResults": []}

    # re-arrange the rules and workflow information in a frequently usable tree structure.
    getUserInputCallResult = getUserInput(inputJson)
    if getUserInputCallResult.get("status") == "false":
        return {"status": "false", "error": getUserInputCallResult.get("error")}
    currentRules = getUserInputCallResult.get("sampleRelationshipsTableInfo")
    userInputInfo = userInput["userInputInfo"]
    validationResults = []

    # create a hash currentlyAvailableWorkflows with workflow name as key and value as a hash of all props of workflows from column-map
    currentlyAvaliableWorkflows={}
    for cmap in currentRules["column-map"]:
        currentlyAvaliableWorkflows[cmap["Workflow"]]=cmap
    # create a hash orderedColumns with column order number as key and value as a hash of all properties of each column from columns
    orderedColumns={}
    for col in currentRules["columns"]:
        orderedColumns[col["Order"]] = col

    # Get cancer types
    cancerTypesListResult = getIRCancerTypesList(inputJson)
    if (cancerTypesListResult["status"] != "true"):
        return cancerTypesListResult
    cancerTypesList = cancerTypesListResult["cancerTypes"]

    # Extracting Gender column from the current rules for validation purpose.
    validGenderList = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Gender"):
            validGenderList = col["Values"]

    # Extracting Relation column from the current rules for validation purpose.
    validRelations = []
    for col in currentRules["columns"]:
        if(col["Name"] == "Relation"):
            validRelations = col["Values"]

    # getting the complete workflow list to extract the relationship type.
    allWorkflowListResult = getWorkflowList(inputJson)
    if (allWorkflowListResult["status"] != "true"):
        return allWorkflowListResult
    allWorkflowList = allWorkflowListResult["userWorkflows"]

    """ some debugging prints for the dev phase
    print "Current Rules"
    print currentRules
    print ""
    print "ordered Columns"
    print orderedColumns
    print ""
    print ""
    print "Order 1"
    if getElementWithKeyValueLD("Order","8", currentRules["columns"]) != None:
        print getElementWithKeyValueLD("Order","8", currentRules["columns"])
    print ""
    print ""
    print "Name Gender"
    print getElementWithKeyValueDD("Name","Gender", orderedColumns)
    print ""
    print ""
    """


    ###################################### This is a mock logic. This is not the real validation code. This is for test only
    ###################################### This can be enabled or disabled using the control variable just below.
    mockLogic = 0
    if mockLogic == 1:
        #for 4.0, for now, return validation results based on a mock logic .
        row = 1
        for uip in userInputInfo:
            if "row" in uip:
                resultRow={"row": uip["row"]}
            else:
                resultRow={"row":str(row)}
            if uip["Gender"] == "Unknown" :
                resultRow["errorMessage"]="For the time being... ERROR:  Gender cannot be Unknown"
            if uip["setid"].find("0_") != -1  :
                resultRow["warningMessage"]="For the time being... WARNING:  setid is still zero .. did you forget to set it correctly?"
            validationResults.append(resultRow)
            row = row + 1
        return {"status": "true", "error": "none", "validationResults": validationResults}
    ######################################
    ######################################



    setidHash={}
    rowErrors={}
    rowWarnings={}
    rowHighlightableFields={}
    uniqueSamples={}
    analysisCost={}
    analysisCost["workflowCosts"]=[]
    similar_sample_name_check_for_wf={}
    immune_rep_multi_wf=[]
    unique_sample_workflow_list = []
    unique_sample_wf_dict={}
    duplicate_sample_exists = False
    isImmuneRep = False

    row = 1
    for uip in userInputInfo:
        # make a row number if not provided, else use whats provided as rownumber.
        if "row" not in uip:
            uip["row"]=str(row)
        rowStr = uip["row"]
        # register such a row in the error bucket  and warning buckets.. basically create two holder arrays in those buckets.  Also do the same for highlightableFields
        if  rowStr not in rowErrors:
            rowErrors[rowStr]=[]
        if  rowStr not in rowWarnings:
            rowWarnings[rowStr]=[]
        if  rowStr not in rowHighlightableFields:
            rowHighlightableFields[rowStr]=[]

        # some known key translations on the uip, before uip can be used for validations
        if  "setid" in uip :
            uip["SetID"] = uip["setid"]
        if  "RelationshipType" not in uip :
            if  "Relation" in uip :
                uip["RelationshipType"] = uip["Relation"]
            if  "RelationRole" in uip :
                uip["Relation"] = uip["RelationRole"]
        if uip["Workflow"] == "Upload Only":
            uip["Workflow"] = ""
        if uip["Workflow"] !="":
            if uip["Workflow"] in currentlyAvaliableWorkflows:
                #uip["ApplicationType"] = currentlyAvaliableWorkflows[uip["Workflow"]]["ApplicationType"]
                #uip["DNA_RNA_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["DNA_RNA_Workflow"]
                #uip["OCP_Workflow"] = currentlyAvaliableWorkflows[uip["Workflow"]]["OCP_Workflow"]
                if "RelationshipType" in currentlyAvaliableWorkflows[uip["Workflow"]]:
                    currentWorkflowDetails = currentlyAvaliableWorkflows[uip["Workflow"]]
                    if uip["RelationshipType"] and (currentWorkflowDetails["RelationshipType"] != uip["RelationshipType"]):
                        msg="selected relation "+ uip["RelationshipType"] + " is not valid." + rowStr
                        inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                        continue

                # another temporary check which is not required if all the parameters of workflow  were  properly handed off from TS
                if "RelationshipType" not in uip :
                    msg="INTERNAL ERROR:  For selected workflow "+ uip["Workflow"] + ", an internal key  RelationshipType is missing for row " + rowStr
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue

                #bring in all the workflow parameter so far available, into the uip hash.
                for k in  currentlyAvaliableWorkflows[uip["Workflow"]] :
                    uip[k] = currentlyAvaliableWorkflows[uip["Workflow"]][k]

                #Override cellularity percentage based on DNA RNA workflows
                if (uip["DNA_RNA_Workflow"] == "DNA_RNA"):
                    if (uip["nucleotideType"] == "DNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "1"
                    elif (uip["nucleotideType"] == "RNA"):
                        uip["CELLULARITY_PCT_REQUIRED"] = "0"

                if ("tag_NO_CNV" in uip and uip["tag_NO_CNV"] == "true"):
                    uip["CELLULARITY_PCT_REQUIRED"] = "0"

                if ("tag_TAGSEQ" in uip and uip["tag_TAGSEQ"] == "true"):
                    uip["CELLULARITY_PCT_REQUIRED"] = "0"

            else:
                uip["ApplicationType"] = "unknown"
                msg="selected workflow "+ uip["Workflow"] + " is not available for this IR user account at this time" + rowStr
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                continue
        if  "nucleotideType" in uip :
            uip["NucleotideType"] = uip["nucleotideType"]
        if  "NucleotideType" not in uip :
            uip["NucleotideType"] = ""
        if  "cellularityPct" in uip :
            uip["CellularityPct"] = uip["cellularityPct"]
        if  "CellularityPct" not in uip :
            uip["CellularityPct"] = ""
        if  "cancerType" in uip :
            uip["CancerType"] = uip["cancerType"]
        if  "CancerType" not in uip :
            uip["CancerType"] = ""
        if  "controlType" in uip :
            if uip["controlType"] == "None":
                uip["ControlType"] = ""
            else:
                uip["ControlType"] = uip["controlType"]
        if  "controlType" not in uip :
            uip["ControlType"] = ""
        if  "reference" in uip :
            uip["Reference"] = uip["reference"]
        if  "reference" not in uip :
            uip["Reference"] = ""
        if  "hotSpotRegionBedFile" in uip :
            uip["HotSpotRegionBedFile"] = uip["hotSpotRegionBedFile"]
        if  "hotSpotRegionBedFile" not in uip :
            uip["HotSpotRegionBedFile"] = ""
        if  "targetRegionBedFile" in uip :
            uip["TargetRegionBedFile"] = uip["targetRegionBedFile"]
        if  "targetRegionBedFile" not in uip :
            uip["TargetRegionBedFile"] = ""


        if(uip["CancerType"] and (uip["CancerType"] not in cancerTypesList)):
            msg="selected cancer type "+ uip["CancerType"] + " is not valid for this IR user account. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["Gender"] and (uip["Gender"] not in validGenderList)):
            msg="selected gender type "+ uip["Gender"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #continue

        if(uip["RelationRole"] and (uip["RelationRole"] not in validRelations)):
            msg="selected relation role "+ uip["RelationRole"] + " is not valid. " + rowStr
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            continue

        # all given sampleNames should be unique   TBD Jose   this requirement is going away.. need to safely remove this part. First, IRU plugin should be corrected before correcting this rule.
        if uip["sample"] not in uniqueSamples:
            uniqueSamples[uip["sample"]] = uip  #later if its a three level then make it into an array of uips
            unique_sample_row_no = uniqueSamples[uip["sample"]]["row"]
            for rec in userInputInfo:
                if rec["row"] == unique_sample_row_no:
                    unique_sample_workflow_list.append(rec["Workflow"])
            unique_sample_wf_dict[unique_sample_row_no] = unique_sample_workflow_list
            unique_sample_wf_dict["SetID"] = uip["SetID"]
            unique_sample_wf_dict["sample"] = uip["sample"]
            unique_sample_wf_dict["row"] = uip["row"]
            write_debug_log(unique_sample_wf_dict)
        else:
            duplicateSamplesExists = True
            theOtherUip = uniqueSamples[uip["sample"]]
            theOtherRowStr = theOtherUip["row"]
            theOtherSetid = theOtherUip["setid"]
            theOtherRelation = theOtherUip["Relation"]
            theOtherRelationShipType = theOtherUip["RelationshipType"]
            theOtherGender = theOtherUip["Gender"]
            if  "controlType" in theOtherUip :
                if theOtherUip["controlType"] == "None":
                    theOtherUipControlType = ""
                else:
                    theOtherUipControlType = theOtherUip["controlType"]
            if  "controlType" not in theOtherUip :
                theOtherUipControlType = ""
            if  "reference" in theOtherUip :
                theOtherUipReference = theOtherUip["reference"]
            if  "reference" not in theOtherUip :
                theOtherUipReference = ""
            if  "hotSpotRegionBedFile" in theOtherUip :
                theOtherUipHotSpotRegionBedFile = theOtherUip["hotSpotRegionBedFile"]
            if  "hotSpotRegionBedFile" not in theOtherUip :
                theOtherUipHotSpotRegionBedFile = ""
            if  "targetRegionBedFile" in theOtherUip :
                theOtherUipTargetRegionBedFile = theOtherUip["targetRegionBedFile"]
            if  "targetRegionBedFile" not in theOtherUip :
                theOtherUipTargetRegionBedFile = ""

            write_debug_log("OtherSetid: " + theOtherSetid + ", theOtherRelation: " + theOtherRelation + ", theOtherRelationShipType: " + theOtherRelationShipType + ", theOtherGender: " + theOtherGender + ", theOtherControlType: " + theOtherUipControlType + ", theOtherUipReference: " + theOtherUipReference + ", theOtherUipHotSpotRegionBedFile: " + theOtherUipHotSpotRegionBedFile + ", theOtherUipTargetRegionBedFile: " + theOtherUipTargetRegionBedFile)
            write_debug_log("this Setid: " + uip["setid"] + ", Relation: " + uip["Relation"] + ", RelationshipType: " + uip["RelationshipType"] + ", Gender: " + uip["Gender"] + ", ControlType: " + uip["ControlType"] + ", Reference: " + uip["Reference"] + ", HotSpotRegionBedFile: " + uip["HotSpotRegionBedFile"] + ", TargetRegionBedFile: " + uip["TargetRegionBedFile"])

            theOtherDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in theOtherUip:
                theOtherDNA_RNA_Workflow = theOtherUip["DNA_RNA_Workflow"]
            thisDNA_RNA_Workflow = ""
            if "DNA_RNA_Workflow" in uip:
                thisDNA_RNA_Workflow = uip["DNA_RNA_Workflow"]
            theOtherNucleotideType = ""
            if "NucleotideType" in theOtherUip:
                theOtherNucleotideType = theOtherUip["NucleotideType"]
            thisNucleotideType = ""
            if "NucleotideType" in uip:
                thisNucleotideType = uip["NucleotideType"]
            # if the rows are for DNA_RNA workflow, then dont complain .. just pass it along..
            #debug print  uip["row"] +" == " + theOtherRowStr + " samplename similarity  " + uip["DNA_RNA_Workflow"] + " == "+ theOtherDNA_RNA_Workflow
            if (       ((uip["Workflow"]=="Upload Only") or (uip["Workflow"] == "")) and (thisNucleotideType != theOtherNucleotideType)     ):
                duplicateSamplesExists = False
            if (       (uip["setid"] == theOtherSetid) and (thisDNA_RNA_Workflow == theOtherDNA_RNA_Workflow ) and (thisDNA_RNA_Workflow == "DNA_RNA")      ):
                duplicateSamplesExists = False

            fieldValueDiffers = False
            if (uip["setid"] != theOtherSetid):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)      # TDB: Highlighting fields in these below conditions is not working, Check later.
            if (uip["Relation"] != theOtherRelation):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Relation", rowHighlightableFields)
            if (uip["RelationshipType"] != theOtherRelationShipType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
            if (uip["Gender"] != theOtherGender):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Gender", rowHighlightableFields)
            if (uip["ControlType"] != theOtherUipControlType):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "ControlType", rowHighlightableFields)
            if (uip["Reference"] != theOtherUipReference):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "Reference", rowHighlightableFields)
            if (uip["HotSpotRegionBedFile"] != theOtherUipHotSpotRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "HotSpotRegionBedFile", rowHighlightableFields)
            if (uip["TargetRegionBedFile"] != theOtherUipTargetRegionBedFile):
                fieldValueDiffers = True
                inputValidationHighlightFieldHandle(rowStr, "TargetRegionBedFile", rowHighlightableFields)
            if not unique_sample_wf_dict.has_key(str(uip["row"])):
                immune_rep_multi_wf.append(uip["Workflow"])
                similar_sample_name_check_for_wf[uip["row"]] = immune_rep_multi_wf
                similar_sample_name_check_for_wf["SetID"] = uip["SetID"]
                similar_sample_name_check_for_wf["sample"] = uip["sample"]
                similar_sample_name_check_for_wf["row"] = uip["row"]
                write_debug_log(similar_sample_name_check_for_wf)
                duplicate_sample_exists = True



            if not fieldValueDiffers:
                duplicateSamplesExists = False


            if duplicateSamplesExists :
                msg ="Sample name "+uip["sample"] + " in row "+ rowStr+" is also in row "+theOtherRowStr+", Please change the sample name. Or, If you intend to use multi-barcodes per sample then please make sure all the other field values are same for all corresponding rows."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
                continue
            # else dont flag an error

        # see whether variant Caller plugin is required or not.
        if  (   ("ApplicationType" in uip)  and  (uip["ApplicationType"] == "Annotation")   ) :
            requiresVariantCallerPlugin = True
            if (  (isVariantCallerSelected != "Unknown")  and (isVariantCallerConfigured != "Unknown")  ):
                if (isVariantCallerSelected != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. Please select and configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue
                if (isVariantCallerConfigured != "True"):
                    msg ="Workflow "+ uip["Workflow"] +" in row("+ rowStr+") requires selecting and configuring Variant Caller plugin. The Variant Caller plugin is selected, but not configured. Please configure Variant Caller plugin before using this workflow."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    continue


        # if setid is empty or it starts with underscore , then dont validate and dont include this row in setid hash for further validations.
        if (   (uip["SetID"].startswith("_")) or   (uip["SetID"]=="")  ):
            msg ="SetID in row("+ rowStr+") should not be empty or start with an underscore character. Please update the SetID."
            inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
            inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
            continue
        # save the workflow information of the record on the setID.. also check workflow mismatch with previous row of the same setid
        setid = uip["SetID"]
        if  setid not in setidHash:
            setidHash[setid] = {}
            setidHash[setid]["records"] =[]
            setidHash[setid]["firstRecordRow"]=uip["row"]
            if uip["Workflow"] == "":
                setidHash[setid]["firstWorkflow"]=""
                setidHash[setid]["firstApplicationType"]=""
                setidHash[setid]["firstRelationshipType"]=""
                setidHash[setid]["firstRecordDNA_RNA"]=""
            else:
                setidHash[setid]["firstWorkflow"]=uip["Workflow"]
                setidHash[setid]["firstApplicationType"]=uip["ApplicationType"]
                setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
                setidHash[setid]["firstRecordDNA_RNA"]=uip["DNA_RNA_Workflow"]
            if "AllowMultipleRoleRecords" in uip :
                setidHash[setid]["firstAllowMultipleRoleRecords"]=uip["AllowMultipleRoleRecords"]
        else:
            if not bool(setidHash[setid]["firstRelationshipType"]):
                setidHash[setid]["firstRelationshipType"]=uip["RelationshipType"]
            if not bool(setidHash[setid]["firstWorkflow"]):
                setidHash[setid]["firstWorkflow"]=uip["Workflow"]
            previousRow = setidHash[setid]["firstRecordRow"]
            expectedWorkflow = setidHash[setid]["firstWorkflow"]
            expectedRelationshipType = setidHash[setid]["firstRelationshipType"]
            expectedApplicationType = setidHash[setid]["firstApplicationType"]
            #print  uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType

            if expectedWorkflow != uip["Workflow"]:
                isValidationAllowed = isMultiWorkflowSelectionEnabled(uip["ApplicationType"])
                if not bool(isValidationAllowed):
                    msg="Selected workflow "+ uip["Workflow"] + " does not match a previous sample with the same SetID, with workflow "+ expectedWorkflow +" in row "+ previousRow+ ". Either change this workflow to match the previous workflow selection for the this SetID, or change the SetiD to a new value if you intend this sample to be used in a different IR analysis."
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(rowStr, "setid", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)
            elif expectedRelationshipType != uip["RelationshipType"]:
                #print  "error on " + uip["row"] +" == " + previousRow + " set id similarity  " + uip["RelationshipType"] + " == "+ expectedRelationshipType
                msg="INTERNAL ERROR:  RelationshipType "+ uip["RelationshipType"] + " of the selected workflow, does not match a previous sample with the same SetID, with RelationshipType "+ expectedRelationshipType +" in row "+ previousRow+ "."
                inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(rowStr, "RelationshipType", rowHighlightableFields)
                inputValidationHighlightFieldHandle(rowStr, "Workflow", rowHighlightableFields)
            #elif expectedApplicationType != uip["ApplicationType"]:  #TBD add similar internal error
        setidHash[setid]["records"].append(uip)

        # check if sample already exists on IR at this time and give a warning..
        inputJson["sampleName"] = uip["sample"]
        if uip["sample"] not in uniqueSamples:    # no need to repeat if the check has been done for the same sample name on an earlier row.
            sampleExistsCallResults = sampleExistsOnIR(inputJson)
            if sampleExistsCallResults.get("error") != "":
                if sampleExistsCallResults.get("status") == "true":
                    msg="sample name "+ uip["sample"] + " already exists in Ion Reporter "
                    inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)

        # check all the generic rules for this uip .. the results of the check goes into the hashes provided as arguments.
        validateAllRulesOnRecord_5_18(currentRules["restrictionRules"], uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields)
        if row == 1:
            if "firstApplicationType" in setidHash[setid]:
                if (setidHash[setid]["firstApplicationType"] == "ImmuneRepertoire") :
                    isImmuneRep = True

        row = row + 1

    if duplicate_sample_exists:
        if similar_sample_name_check_for_wf["SetID"] == unique_sample_wf_dict["SetID"]:
            if similar_sample_name_check_for_wf["sample"] == unique_sample_wf_dict["sample"]:
                sample_wf_list1=[]
                sample_wf_list2=[]
                for k,v in similar_sample_name_check_for_wf.items():
                    if type(similar_sample_name_check_for_wf[k]) == list:
                        sample_wf_list1.append(similar_sample_name_check_for_wf[k])
                for k,v in unique_sample_wf_dict.items():
                    if type(unique_sample_wf_dict[k]) == list:
                        sample_wf_list2.append(unique_sample_wf_dict[k])
                result1_list = sample_wf_list1[0]
                result2_list = sample_wf_list2[0]
                write_debug_log(result1_list)
                write_debug_log(result2_list)
                for items in result1_list:
                    if items not in result2_list:
                        msg ="Sample name "+similar_sample_name_check_for_wf["sample"] + " in row "+ similar_sample_name_check_for_wf["row"]+" is also in row "+unique_sample_wf_dict["row"]+", Please change the sample name. Or, If you intend to use multi-barcodes per sample then please make sure similar workflows are selected in corresponding rows."
                        inputValidationErrorHandle(rowStr, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(rowStr, "sample", rowHighlightableFields)

    # after validations of basic rules look for errors all role requirements, uniqueness in roles, excess number of
    # roles, insufficient number of roles, etc.
    for setid in setidHash:
        # first check all the required roles are there in the given set of records of the set
        rowsLooked = ""
        uniqueSamplesForThisSetID = []

        for record in setidHash[setid]["records"]:
            if record["sample"] not in uniqueSamplesForThisSetID:
                uniqueSamplesForThisSetID.append(record["sample"])


        if "validRelationRoles" in setidHash[setid]:
            for validRole in setidHash[setid]["validRelationRoles"]:
                foundRole=0
                rowsLooked = ""
                for record in setidHash[setid]["records"]:
                    if rowsLooked != "":
                        rowsLooked = rowsLooked + "," + record["row"]
                    else:
                        rowsLooked = record["row"]
                    if validRole == record["Relation"]:   #or RelationRole
                        foundRole = 1
                if foundRole == 0 :
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required RelationRole "+ validRole + " is not found. "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)
            # check if any extra roles exists.  Given that the above test exists for lack of roles, it is sufficient if we
            # verify the total number of roles expected and number of records got, for this setid. If there is a mismatch,
            # it means there are more than the number of roles required.
            #    Use the value of the rowsLooked,  populated from the above loop.
            sizeOfRequiredRoles = len(setidHash[setid]["validRelationRoles"])
            numRecordsForThisSetId = len(setidHash[setid]["records"])
            numOfUniqueSamples = len(uniqueSamplesForThisSetID)
            singleSampleApplicationTypeSet = set(["Amplicon Sequencing","Amplicon Low Frequency Sequencing","Low-Coverage Whole Genome Sequencing","Oncomine_RNA_Fusion","Annotation","Targeted Resequencing", \
                                                  "AmpliSeqHD Single Pool","Low Frequency Resequencing","Mutational Load","ONCOLOGY_LIQUID_BIOPSY","ImmuneRepertoire","Genomic Resequencing"])
            if ( (setidHash[setid]["firstApplicationType"] in singleSampleApplicationTypeSet) and (numOfUniqueSamples > sizeOfRequiredRoles)) :
                msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of samples are found. Expected number of samples is " + str(sizeOfRequiredRoles) + ". "
                if   rowsLooked != "" :
                    if rowsLooked.find(",") != -1  :
                        msg = msg + "Please check the rows " + rowsLooked
                    else:
                        msg = msg + "Please check the row " + rowsLooked
                inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Sample", rowHighlightableFields)

            if (numRecordsForThisSetId > sizeOfRequiredRoles):
                complainAboutTooManyRoles = True

                uniqueRoles = []
                for uipInRecords in setidHash[setid]["records"]:
                    if (uipInRecords["Relation"] not in uniqueRoles):
                        uniqueRoles.append(uipInRecords["Relation"])
                if(len(uniqueRoles) == sizeOfRequiredRoles):
                    complainAboutTooManyRoles = False

                # ignore this check if the application type or other workflow settings already allws multi roles
                if "firstAllowMultipleRoleRecords" in setidHash[setid]:
                    if setidHash[setid]["firstAllowMultipleRoleRecords"] == "true":
                        complainAboutTooManyRoles = False
                # for DNA_RNA flag, its not the roles to be evaluated, its the nucleotideTypes to be evaluated.
                if setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA":
                    complainAboutTooManyRoles = False

                if complainAboutTooManyRoles:
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of RelationRoles is found. Expected number of roles is " + str(sizeOfRequiredRoles) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Relation", rowHighlightableFields)

        ##
        # validate the nucleotidetypes, similar to the roles.
        # first check all the required nucleotides are there in the given set of records of the set
        #    Use the value of the rowsLooked,  populated from the above loop.
        if ( isImmuneRep == True ):
            if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "DNA") ):
                # for validNucleotide in setidHash[setid]["validNucleotideTypes"]:
                #     foundNucleotide=0
                for record in setidHash[setid]["records"]:
                    foundNucleotide = 0
                    if (record["DNA_RNA_Workflow"] == record["NucleotideType"]):   #or NucleotideType
                        foundNucleotide = 1
                    if foundNucleotide == 0 :
                        msg="For workflow " + record["Workflow"] +", a required NucleotideType "+ record["NucleotideType"] + " is not found. "
                        # AS per demo comments removing this code.
                        #                     if   rowsLooked != "" :
                        #                         if rowsLooked.find(",") != -1  :
                        #                             msg = msg + "Please check the rows " + rowsLooked
                        #                         else:
                        #                             msg = msg + "Please check the row " + rowsLooked
                        inputValidationErrorHandle(record["row"], "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                        inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)
                # check if any extra nucleotides exists.  Given that the above test exists for missing nucleotides, it is sufficient if we
                # verify the total number of nucleotides expected and number of records got, for this setid. If there is a mismatch,
                # it means there are more than the number of nucleotides required.
                #    Use the value of the rowsLooked,  populated from the above loop.
                sizeOfRequiredNucleotides = len(setidHash[setid]["validNucleotideTypes"])
                numberOfUniqueSamples = len(uniqueSamplesForThisSetID)
                #numRecordsForThisSetId = len(setidHash[setid]["records"])   #already done as part of roles check
                if (numberOfUniqueSamples > sizeOfRequiredNucleotides):
                    msg="For workflow " + setidHash[setid]["firstWorkflow"] + ", more than the required number of Nucleotides is found. Expected number of Nucleotides is " + str(sizeOfRequiredNucleotides) + ". "
                    if   rowsLooked != "" :
                        if rowsLooked.find(",") != -1  :
                            msg = msg + "Please check the rows " + rowsLooked
                        else:
                            msg = msg + "Please check the row " + rowsLooked
                    inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                    inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)
        else:
            if (   (setidHash[setid]["firstRecordDNA_RNA"] == "DNA_RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "RNA")  or  (setidHash[setid]["firstRecordDNA_RNA"] == "DNA") ):
                for validNucleotide in setidHash[setid]["validNucleotideTypes"]:
                    foundNucleotide=0
                    for record in setidHash[setid]["records"]:
                        if validNucleotide == record["NucleotideType"]:   #or NucleotideType
                            foundNucleotide = 1

                    if foundNucleotide == 0 :
                        msg="For workflow " + setidHash[setid]["firstWorkflow"] +", a required NucleotideType "+ validNucleotide + " is not found. "
                        if   rowsLooked != "" :
                            if rowsLooked.find(",") != -1  :
                                msg = msg + "Please check the rows " + rowsLooked
                            else:
                                msg = msg + "Please check the row " + rowsLooked
                        inputValidationErrorHandle(setidHash[setid]["firstRecordRow"], "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "Workflow", rowHighlightableFields)
                        inputValidationHighlightFieldHandle(setidHash[setid]["firstRecordRow"], "NucleotideType", rowHighlightableFields)

        # calculate the cost of the analysis
        cost={}
        cost["row"]=setidHash[setid]["firstRecordRow"]
        cost["workflow"]=setidHash[setid]["firstWorkflow"]
        cost["cost"]="50.00"     # TBD  actually, get it from IR. There are now APIs available.. TS is not yet popping this to user before plan submission.
        analysisCost["workflowCosts"].append(cost)

    analysisCost["totalCost"]="2739.99"   # TBD need to have a few lines to add the individual cost... TS is not yet popping this to user before plan submission.
    analysisCost["text1"]="The following are the details of the analysis planned on the IonReporter, and their associated cost estimates."
    analysisCost["text2"]="Press OK if you have reviewed and agree to the estimated costs and wish to continue with the planned IR analysis, or press CANCEL to make modifications."





    """
    print ""
    print ""
    print "userInputInfo"
    print userInputInfo
    print ""
    print ""
    """
    #print ""
    #print ""
    #print "setidHash"
    #print setidHash
    #print ""
    #print ""

    # consolidate the  errors and warnings per row and return the results
    foundAtLeastOneError = 0
    message=""
    valid = "false"
    for uip in userInputInfo:
        rowstr=uip["row"]
        emsg=""
        wmsg=""
        if rowstr in rowErrors:
            for e in  rowErrors[rowstr]:
                foundAtLeastOneError =1
                if (message.find(e) == -1):
		    emsg = emsg + e + " ; "
		    message = message + e
                    valid = "true"
        if rowstr in rowWarnings:
            for w in  rowWarnings[rowstr]:
                wmsg = wmsg + w + " ; "
        k={"row":rowstr, "errorMessage":emsg, "warningMessage":wmsg, "errors": rowErrors[rowstr], "warnings": rowWarnings[rowstr]}
        if rowstr in rowHighlightableFields:
            k["highlightableFields"]=rowHighlightableFields[rowstr]
        else:
            k["highlightableFields"]=[]
	if (valid == "true"):
            if not validationResults:
                validationResults.append(k)
            else:
                for index, error_result in enumerate(validationResults):
                    k["errorMessage"] = ""
                    if k["errors"] != error_result["errors"]:
                        validationResults.append(k)
                        validationResults=  [item for index, item in enumerate(validationResults) if item not in validationResults[index + 1:]]




    # forumulate a few constant advices for use on certain conditions, to TS users
    advices={}
    #advices["onTooManyErrors"]= "Looks like there are some errors on this page. If you are not sure of the workflow requirements, you can opt to only upload the samples to IR and not run any IR analysis on those samples at this time, by not selecting any workflow on the Workflow column of this tabulation. You can later find the sample on the IR, and launch IR analysis on it later, by logging into the IR application."
    #advices["onTooManyErrors"]= "There are errors on this page. If you only want to upload samples to Ion Reporter and not perform an Ion Reporter analysis at this time, you do not need to select a Workflow. When you are ready to launch an Ion Reporter analysis, you must log into Ion Reporter and select the samples to analyze."
    advices["onTooManyErrors"]= "<html> <body> There are errors on this page. To remove them, either: <br> &nbsp;&nbsp;1) Change the Workflow to &quot;Upload Only&quot; for affected samples. Analyses will not be automatically launched in Ion Reporter.<br> &nbsp;&nbsp;2) Correct all errors to ensure autolaunch of correct analyses in Ion Reporter.<br> Visit the Torrent Suite documentation at <a href=/ion-docs/Home.html > docs </a>  for examples. </body> </html>"

    # forumulate a few conditions, which may be required beyond this validation.
    conditions={}
    conditions["requiresVariantCallerPlugin"]=requiresVariantCallerPlugin


    #true/false return code is reserved for error in executing the functionality itself, and not the condition of the results itself.
    # say if there are networking errors, talking to IR, etc will return false. otherwise, return pure results. The results internally
    # may contain errors, which is to be interpretted by the caller. If there are other helpful error info regarding the results itsef,
    # then additional variables may be used to reflect metadata about the results. the status/error flags may be used to reflect the
    # status of the call itself.
    #if (foundAtLeastOneError == 1):
    #    return {"status": "false", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    #else:
    #    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost}
    return {"status": "true", "error": "none", "validationResults": validationResults, "cost":analysisCost, "advices": advices,
            "conditions": conditions
            }

    """
    # if we want to implement this logic in grws, then here is the interface code.  But currently it is not yet implemented there.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/TSUserInputValidate/"
        hdrs = {'Authorization': token}
        resp = requests.post(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        result = {}
        if resp.status_code == requests.codes.ok:
            result = json.loads(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            raise Exception("IR WebService Error Code " + str(resp.status_code))
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "validationResults": result}
    """

def isMultiWorkflowSelectionEnabled(applicationType):
    allowedAppTypes = readPropertyFile()
    allowedAppTypesArray = allowedAppTypes.split(",")
    if applicationType in allowedAppTypesArray:
      return True
    return False

def readPropertyFile():
    separator = "="
    keys = {}
    propertyFile = get_plugin_dir() + "/IonReporterUploader.properties"
    with open(propertyFile) as f:
        for line in f:
            if separator in line:
                name, value = line.split(separator, 1)
                keys[name.strip()] = value.strip()
    return keys['application.type']

def validateAllRulesOnRecord_5_16(rules, uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                #msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                #inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                continue

            andForExists = 0
            if "AndFor" in rule:
                if rule["AndFor"]["Name"] not in uip:
                    continue
                else:
                    andForExists = 1

            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1
                    if valueCheck == 1 :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid
                            #inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kValid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
                        # another small hardcoded update into the setidHash for later evaluation of the nucleotideType  uniqueness
                        if kValid == "NucleotideType":
                            if setid  in setidHash:
                                if "validNucleotideTypes" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validNucleotideTypes"] = vValid   # this is actually list of valid nucleotideTypes
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if valueCheck == 1 :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid
                            #inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kInvalid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "NonEmpty" in rule:
                kFor=rule["For"]["Name"]
                vFor=rule["For"]["Value"]
                kNonEmpty=rule["NonEmpty"]["Name"]
                #print  "non empty validating   kfor " +kFor  + " vFor "+ vFor + "  kNonEmpty "+ kNonEmpty
                #if kFor not in uip :
                #    print  "kFor not in uip   "  + " kFor "+ kFor
                #    continue
                if uip[kFor] == vFor :
                    if (   (kNonEmpty not in uip)   or  (uip[kNonEmpty] == "")   ):
                        #msg="Empty value found for " + kNonEmpty + " When "+ kFor + " is \"" + vFor +"\"."
                        msg="Empty value found for " + kNonEmpty
                        inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(row, kNonEmpty, rowHighlightableFields)
                        inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "Disabled" in rule:
                pass
            else:
                msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

def validateAllRulesOnRecord_5_18(rules, uip, setidHash, rowErrors, rowWarnings,rowHighlightableFields):
    row=uip["row"]
    setid=uip["SetID"]
    for  rule in rules:
        # find the rule Number
        if "ruleNumber" not in rule:
            msg="INTERNAL ERROR  Incompatible validation rules for this version of IRU. ruleNumber not specified in one of the rules."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
            ruleNum="unkhown"
        else:
            ruleNum=rule["ruleNumber"]

        # find the validation type
        if "validationType" in rule:
            validationType = rule["validationType"]
        else:
            validationType = "error"
        if validationType not in ["error", "warn"]:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. unrecognized validationType \"" + validationType + "\""
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

        # execute all the rules
        if "For" in rule:
            if rule["For"]["Name"] not in uip:
                #msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"For\" field \"" + rule["For"]["Name"] + "\""
                #inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                continue

            andForExists = 0
            if "AndFor" in rule:
                if rule["AndFor"]["Name"] not in uip:
                    continue
                else:
                    andForExists = 1

            if "Valid" in rule:
                if rule["Valid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Valid\"field \"" + rule["Valid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kValid=rule["Valid"]["Name"]
                    vValid=rule["Valid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1
                    if valueCheck == 1 :
                        if uip[kValid] not in vValid :
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid + " When "+ kFor + " is \"" + vFor +"\"."
                            #msg="Incorrect value \"" + uip[kValid] + "\" found for " + kValid
                            #inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kValid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
                        # a small hardcoded update into the setidHash for later evaluation of the role uniqueness
                        if kValid == "Relation":
                            if setid  in setidHash:
                                if "validRelationRoles" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validRelationRoles"] = vValid   # this is actually roles
                        # another small hardcoded update into the setidHash for later evaluation of the nucleotideType  uniqueness
                        if kValid == "NucleotideType":
                            if setid  in setidHash:
                                if "validNucleotideTypes" not in setidHash[setid]:
                                    #print  "saving   row " +row + "  setid " + setid + "  kfor " +kFor  + " vFor "+ vFor + "  kValid "+ kValid
                                    setidHash[setid]["validNucleotideTypes"] = vValid   # this is actually list of valid nucleotideTypes
            elif "Invalid" in rule:
                if rule["Invalid"]["Name"] not in uip:
                    msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of TSS. No such \"Invalid\" field \"" + rule["Invalid"]["Name"] + "\""
                    inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                else:
                    kFor=rule["For"]["Name"]
                    vFor=rule["For"]["Value"]
                    kInvalid=rule["Invalid"]["Name"]
                    vInvalid=rule["Invalid"]["Values"]

                    kAndFor=""
                    vAndFor=""
                    if andForExists == 1:
                        kAndFor=rule["AndFor"]["Name"]
                        vAndFor=rule["AndFor"]["Value"]

                    valueCheck = 0
                    if andForExists == 0 :
                        if uip[kFor] == vFor :
                            valueCheck = 1
                    else :
                        if (uip[kFor] == vFor) and (uip[kAndFor] == vAndFor) :
                            valueCheck = 1

                    #print  "validating   kfor " +kFor  + " vFor "+ vFor + "  kInvalid "+ kInvalid
                    if valueCheck == 1 :
                        if uip[kInvalid] in vInvalid :
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"   rule # "+ ruleNum
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid + " When "+ kFor + " is \"" + vFor +"\"."
                            #msg="Incorrect value \"" + uip[kInvalid] + "\" found for " + kInvalid
                            #inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings)
                            inputValidationHighlightFieldHandle(row, kInvalid, rowHighlightableFields)
                            inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "NonEmpty" in rule:
                kFor=rule["For"]["Name"]
                vFor=rule["For"]["Value"]
                kNonEmpty=rule["NonEmpty"]["Name"]
                #print  "non empty validating   kfor " +kFor  + " vFor "+ vFor + "  kNonEmpty "+ kNonEmpty
                #if kFor not in uip :
                #    print  "kFor not in uip   "  + " kFor "+ kFor
                #    continue
                if uip[kFor] == vFor :
                    if (   (kNonEmpty not in uip)   or  (uip[kNonEmpty] == "")   ):
                        #msg="Empty value found for " + kNonEmpty + " When "+ kFor + " is \"" + vFor +"\"."
                        msg="Empty value found for " + kNonEmpty
                        inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
                        inputValidationHighlightFieldHandle(row, kNonEmpty, rowHighlightableFields)
                        inputValidationHighlightFieldHandle(row, kFor, rowHighlightableFields)
            elif "Disabled" in rule:
                pass
            else:
                msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. \"For\" specified without a \"Valid\" or \"Invalid\" tag."
                inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)
        else:
            msg="INTERNAL ERROR ON RULE # "+ruleNum+"   Incompatible validation rules for this version of IRU. No action provided on this rule."
            inputValidationErrorHandle(row, "error", msg, rowErrors, rowWarnings)

def inputValidationErrorHandle(row, validationType, msg, rowErrors, rowWarnings):
    if validationType == "error":
        value_list = rowErrors[str(row)]
        if str(msg) not in value_list:
            rowErrors[row].append(msg)
    elif validationType == "warn":
        rowWarnings[row].append(msg)

def inputValidationHighlightFieldHandle(row, fieldName, rowHighlightableFields):
    # we now some fields are not being displayed in the TS planning page.
    # They are not user visible fields. They arehidden fields used only for
    # rule validation purposes. So no use sending back such fields for user
    # visibility highlights.
    ignorableFieldsThatAreHiddenFromUser=["RelationshipType","ApplicationType"]
    if fieldName in ignorableFieldsThatAreHiddenFromUser:
        return

    # and in some cases, this may have been already called for this field as
    # part of some other error or warning. So block multiple appends of the same
    # fieldName into the array
    if fieldName not in rowHighlightableFields[row]:
        rowHighlightableFields[row].append(fieldName)


def getIRGUIBaseURL(inputJson):
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"
    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "false",
                "error": "Workflow Creation UI redirection to IR is not supported for this version of IR " + version,
                "IRGUIBaseURL": ""}

    # for now, return a hardcoded version of the url for 40 production.  The url returned from IR is wrong.. 
    #if (   (version == "40") and (server == "40.dataloader.ionreporter.lifetechnologies.com")  ):
    #    returnUrl = protocol + "://" + "ionreporter.lifetechnologies.com" + ":" + port
    #    return {"status": "true", "error": "none", "IRGUIBaseURL": returnUrl,"version":version}

    # for now, return a hardcoded debug version of the url, because there are still configuraiton issues in the local IR servers.
    #returnUrl = protocol + "://" + server + ":" + port
    #return {"status": "true", "error": "none", "IRGUIBaseURL": returnUrl,"version":version}


    #curl ${CURLOPT}  ${protocol}://${server}:${port}/grws_1_2/data/getIrGUIUrl
    url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/getIrGUIUrl"
    #cmd="curl -ks    -H Authorization:"+token  +   " -H Version:"+version   +   " "+url
    cmd="curl -ks -3     "+url      #actually, this much will do for this webservice. token not required.
    result = get_httpResponseFromSystemTools(cmd)
    if (result["status"] !="true"):
        cmd="curl -ks    "+url      #actually, this much will do for this webservice. token not required.
        result = get_httpResponseFromSystemTools(cmd)
        if (result["status"] !="true"):
            return result
    return {"status": "true", "error": "none", "IRGUIBaseURL": result["stdout"], "version":version}



    #get the correct ui server address, port and protocol from the grws and use that one instead of using iru-server's address.
    try:
        url = protocol + "://" + server + ":" + port + "/" + grwsPath + "/data/getIrGUIUrl"
        hdrs = {'Authorization': token}
        resp = requests.get(url, verify=False, headers=hdrs,timeout=30)  #timeout is in seconds
        #result = {}
        if resp.status_code == requests.codes.ok:
            #returnUrl = json.loads(resp.text)
            returnUrl =str(resp.text)
        else:
            #raise Exception ("IR WebService Error Code " + str(resp.status_code))
            return {"status": "false", "error":"IR WebService Error Code " + str(resp.status_code)}
    except requests.exceptions.Timeout, e:
        return {"status": "false", "error": "Timeout"}
    except requests.exceptions.ConnectionError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.HTTPError, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except requests.exceptions.RequestException, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    except Exception, e:
        #raise Exception("Error Code " + str(e))
        return {"status": "false", "error": str(e)}
    return {"status": "true", "error": "none", "IRGUIBaseURL": returnUrl, "version":version}

def getWorkflowCreationLandingPageURL(inputJson):
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"
    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "false",
                "error": "Workflow Creation UI redirection to IR is not supported for this version of IR " + version,
                "workflowCreationLandingPageURL": "",
                "version": version}

    baseURLResult = getIRGUIBaseURL(inputJson)
    if baseURLResult["status"] == "false":
         return baseURLResult
    urlPart1 = baseURLResult["IRGUIBaseURL"]

    queryParams = {'authToken': token}
    urlEncodedQueryParams = urllib.urlencode(queryParams)
    # a debug version of the url to return a hardcoded url
    #url2 = protocol + "://" + server + ":" + port + "/ir/secure/workflow.html?" + urlEncodedQueryParams
    #urlPart1 = protocol + "://" + server + ":" + port
    #returnUrl = urlPart1+urlPart2
    #return {"status": "true", "error": "none", "workflowCreationLandingPageURL": returnUrl}
    if version == "40":
        urlPart2 = "/ir/secure/workflow.html?" + urlEncodedQueryParams
    else: #if version == "42": or above
        urlPart2 = "/ir/postauth/workflow.html"

    returnUrl = urlPart1+urlPart2
    return {"status": "true", "error": "none", "workflowCreationLandingPageURL": returnUrl,
            "version": version}


def getWorkflowCreationLandingPageURLBase(inputJson):
    irAccountJson = inputJson["irAccount"]

    protocol = irAccountJson["protocol"]
    server = irAccountJson["server"]
    port = irAccountJson["port"]
    token = irAccountJson["token"]
    version = irAccountJson["version"]
    version = version.split("IR")[1]
    grwsPath = "grws_1_2"
    #if version == "40" :
    #   grwsPath="grws"
    unSupportedIRVersionsForThisFunction = ['10', '12', '14', '16', '18', '20']
    if version in unSupportedIRVersionsForThisFunction:
        return {"status": "false",
                "error": "Workflow Creation UI redirection to IR is not supported for this version of IR " + version,
                "workflowCreationLandingPageURL": "",
                "version": version}

    #queryParams = {'authToken': token}
    #urlEncodedQueryParams = urllib.urlencode(queryParams)
    # a debug version of the url to return a hardcoded url
    #url2 = protocol + "://" + server + ":" + port + "/ir/secure/workflow.html?" + urlEncodedQueryParams
    #urlPart1 = protocol + "://" + server + ":" + port
    #returnUrl = urlPart1+urlPart2
    #return {"status": "true", "error": "none", "workflowCreationLandingPageURL": returnUrl}
    #print "version = " + version

    if version == "40":
        urlPart2 = "/ir/secure/workflow.html"
    else: #if version == "42": or above
        urlPart2 = "/ir/postauth/workflow.html"

    baseURLResult = getIRGUIBaseURL(inputJson)
    if baseURLResult["status"] == "false":
         return baseURLResult
    urlPart1 = baseURLResult["IRGUIBaseURL"]
    returnUrl = urlPart1+urlPart2
    return {"status": "true", "error": "none", "workflowCreationLandingPageURL": returnUrl,
            "version": version, "token": token}

def uploadStatus(bucket):
    """finds all the IRU progress and globs it together
    """
    def proton_progress(plugin_result):
        payload = {
            "pre": {},
            "post": {}
        }
        pre_json_path = os.path.join(plugin_result["path"],"consolidatedStatus", "pre.json")
        post_json_path = os.path.join(plugin_result["path"],"consolidatedStatus", "post.json")
        composite_json = json.load(open(os.path.join(plugin_result["path"],"startplugin.json")))

        try:
            payload["pre"] = json.load(open(pre_json_path))
        except Exception as err:
            print("Failed to load Proton pre.json")

        try:
            post_json = json.load(open(post_json_path))
            payload["post"] = post_json
        except Exception as err:
            print("Failed to load Proton post.json")


        #find the composite block json files
        consolidatedBlockFiles = glob.glob(os.path.join(plugin_result["path"],"consolidatedStatus", "X*.json"))
        consolidatedBlocks = {}

        for consolidatedBlock in consolidatedBlockFiles:
            if os.path.exists(consolidatedBlock):
                localConsolidatedBlock = json.load(open(consolidatedBlock))
                consolidatedBlocks[localConsolidatedBlock["block.id"]] = localConsolidatedBlock

        #find all the blocks
        blockDirs = composite_json["runplugin"]["block_dirs"]

        progress = {}

        totalProgress = 0

        for block in blockDirs:
            #look for a startplugin.json for each block
            block_plugin = glob.glob(os.path.join(block, "plugin_out/*." + plugin_result_id + "/startplugin.json"))
            if block_plugin and os.path.exists(block_plugin[0]):
                #get the block id
                block_id = json.load(open(block_plugin[0]))["runplugin"]["blockId"]

                #now get the progress.json path
                progress_path = os.path.join(os.path.split(block_plugin[0])[0],"progress.json")


                if os.path.exists(progress_path):
                    #include the progress.json as part of the response
                    progress[block_id] = json.load(open(progress_path))
                    #if not don't add anything to the progress
                    totalProgress += float(progress[block_id].get("progress",0))

        payload["blockProgress"] = progress
        payload["numBlocks"] =  composite_json["runplugin"]["numBlocks"]
        payload["consolidatedBlockStatus"] = consolidatedBlocks
        payload["totalProgress"] = totalProgress / float(payload["numBlocks"])
        return payload

    def pgm_progress(plugin_result, progress_path):
        try:
            progress = json.load(open(progress_path))
        except (IOError, ValueError) as err:
            progress = {}
        payload = {
            "totalProgress": progress.get('progress', 0),
            "remainingTime": progress.get('remainingTime', 0),
            "status": progress.get('status', "No Status"),
            "description": progress.get('description', ""),
            "statusCode": progress.get('statusCode', 0)
        }
        return payload

    if "request_get" in bucket:

        plugin_result_id = bucket["request_get"].get("plugin_result_id", False)

        if plugin_result_id:
            #get the plugin results resource from the api
            plugin_result = requests.get("http://localhost/rundb/api/v1/pluginresult/" + plugin_result_id).json()
            progress_path = os.path.join(plugin_result["path"], "post", "progress.json")
            if os.path.exists(progress_path):
                payload = pgm_progress(plugin_result, progress_path)
            else:
                payload = proton_progress(plugin_result)

            return payload

        #if we got all the way down here it failed
        return False

def lastrun(bucket):
    # check whether previous instance of IRU is in-progress
    lockfile = 'iru_status.lock'

    pluginresult = bucket['request_post']['pluginresult']
    current_version = bucket['request_post'].get('version') or bucket['version']
    state = pluginresult['State']

    if current_version != pluginresult['Version']:
        in_progress = False
        msg = 'Previous plugin instance version %s does not match current version' % pluginresult['Version']
    elif state == 'Completed':
        lockpath = os.path.join(pluginresult['Path'],'post',lockfile)
        if os.path.exists(lockpath):
            in_progress = False
            msg = 'Previous plugin instance state is %s, plugin post-level lock exists %s' % (state, lockpath)
        else:
            in_progress = True
            msg = 'Previous plugin instance state is %s, but plugin post-level lock not found %s' % (state, lockpath)
    else:
        in_progress = True if state != 'Error' else False
        msg = 'Previous plugin instance state is %s.' % state

    return {'in_progress':in_progress, 'msg':msg }


def getElementWithKeyValueDD(k,v, dictOfDict):
    for k1 in dictOfDict:
        ele = dictOfDict[k1]
        if k in ele:
            if ele[k] == v:
                return ele
    return None

def getElementWithKeyValueLD(k,v, listOfDict):
    for ele in listOfDict:
        if k in ele:
            if ele[k] == v:
                return ele
    return None

def getGrwsPath(irAccountJson):
    if 'account_type' in irAccountJson:
      accountType = irAccountJson["account_type"]
    else:
      accountType = "ir"

    write_debug_log("getGrwsPath accountType"+ accountType)

    if accountType.find("Genexus") == -1 and accountType.find("ir7") == -1:
      return "grws_1_2"
    else:
      return "grws"


# set to "IonReporterUploader" by default
def getPluginName():
    return pluginName


def setPluginName(x):
    pluginName = x
    return


def getPluginDir():
    return pluginDir


def setPluginDir(x):
    pluginDir = x
    return


if __name__ == "__main__":

    k = {'port': '443',    # this is the one that is used for most of the test cases below
         'protocol': 'https',
         'server': '40.dataloader.ionreporter.thermofisher.com',
         'version': 'IR54',
         'userid': 'ion.reporter@lifetech.com',
         'password': '123456',
         'token': 'rwVcoTeYGfKxItiaWo2lngsV/r0jukG2pLKbZBkAFnlPbjKfPTXLbIhPb47YA9u78'
        }
    c = {}
    c["irAccount"] = k



    l = {'port': '443',
         'protocol': 'https',
         'server': '40.dataloader.ionreporter.lifetechnologies.com',
         'version': 'IR42',
         'userid': 'ion.reporter@lifetech.com',
         'password': '123456',
         'token': 'rwVcoTeYGfKxItiaWo2lngsV/r0jukG2pLKbZBkAFnlPbjKfPTXLbIhPb47YA9u78'
        }
    d = {}
    d["irAccount"] = l



    p={"userInputInfo":[
        {
          "row": "6",
          "Gender": "Male",
          #"cancerType": "Liver Cancer",
          "barcodeId": "IonXpress_011",
          "sample": "pgm-s11",
          "Relation": "Self",
          "RelationRole": "Self",
          "setid": "0__837663e7-f7f8-4334-b14b-dea091dd353b",
          "Workflow": "TargetSeq Exome v2 single sample"
        },
        {
          "row": "95",
          "Workflow": "AmpliSeq Exome tumor-normal pair",
          "Gender": "Unknown",
          "barcodeId": "IonXpress_012",
          "sample": "pgm-s12T",
          #"Relation": "Tumor_Normal",
          "RelationRole": "Tumor",
          "setid": "1__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "96",
          "Workflow": "AmpliSeq Exome tumor-normal pair",
          "Gender": "Unknown",
          "barcodeId": "IonXpress_012",
          "sample": "pgm-s12N",
          "Relation": "Tumor_Normal",
          "RelationRole": "Normal",
          "setid": "1__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "5",
          "Workflow": "AmpliSeq Exome tumor-normal pair",
          "Gender": "Male",
          "barcodeId": "IonXpress_013",
          "sample": "pgm-s12",
          "Relation": "Tumor_Normal",
          "RelationRole": "Tumor",
          "setid": "2__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "9",
          "Workflow": "AmpliSeq Exome tumor-normal pair",
          "Gender": "Male",
          "barcodeId": "IonXpress_012",
          "sample": "pgm-s12n",
          "Relation": "Tumor_Normal",
          "RelationRole": "Normal",
          "setid": "2__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "21",
          "Workflow": "AmpliSeq OCP DNA RNA Fusions",
          #"Workflow": "Upload Only",
          "Gender": "Male",
          "barcodeId": "IonXpress_012",
          "sample": "pgm-s12_dna_rna",
          "Relation": "DNA_RNA",
          "RelationRole": "Self",
          "NucleotideType": "DNA",
          #"cellularityPct": "10",
          #"cancerType": "Liver Cancer",
          "setid": "4__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "22",
          "Workflow": "AmpliSeq OCP DNA RNA Fusions",
          #"Workflow": "Upload Only",
          "Gender": "Male",
          "barcodeId": "IonXpress_012",
          "sample": "pgm-s12_dna_rna",
          "Relation": "DNA_RNA",
          "RelationRole": "Self",
          "NucleotideType": "RNA",
          "cellularityPct": "11",
          "cancerType": "Liver Cancer",
          "setid": "4__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "23",
          "Workflow": "AmpliSeq OCP DNA RNA Fusions",
          "Gender": "Male",
          "barcodeId": "IonXpress_012",
          "sample": "pgm-s13_dna_rna",
          "Relation": "DNA_RNA",
          "RelationRole": "Self",
          "NucleotideType": "RNA",
          "cellularityPct": "10",
          "cancerType": "Liver Cancer",
          "setid": "5__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "24",
          "Workflow": "AmpliSeq OCP DNA RNA Fusions",
          "Gender": "Male",
          "barcodeId": "IonXpress_012",
          "sample": "pgm-s13_dna_rna",
          "Relation": "DNA_RNA",
          "RelationRole": "Self",
          "NucleotideType": "DNA",
          "cellularityPct": "11",
          "cancerType": "Liver Cancer",
          "setid": "5__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "25",
          "Workflow": "AmpliSeq Colon Lung v2 with RNA Lung Fusion paired sample",
          #"Workflow": "Upload Only",
          "Gender": "Male",
          "barcodeId": "IonXpress_012",
          "sample": "pgm-s12_dna_rna",
          "Relation": "DNA_RNA",
          "RelationRole": "Self",
          "NucleotideType": "DNA",
          #"cellularityPct": "10",
          #"cancerType": "Liver Cancer",
          "setid": "4__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "26",
          "Workflow": "AmpliSeq Colon Lung v2 with RNA Lung Fusion paired sample",
          #"Workflow": "Upload Only",
          "Gender": "Male",
          "barcodeId": "IonXpress_012",
          "sample": "pgm-s12_dna_rna",
          "Relation": "DNA_RNA",
          "RelationRole": "Self",
          "NucleotideType": "RNA",
          "cellularityPct": "11",
          "cancerType": "Liver Cancer",
          "setid": "4__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "27",
          "Workflow": "Annotate variants single sample",
          #"Workflow": "Upload Only",
          "Gender": "Male",
          "barcodeId": "IonXpress_013",
          "sample": "2015-03-24_025028_C",
          "Relation": "DNA",
          "RelationRole": "Self",
          "NucleotideType": "DNA",
          "cellularityPct": "11",
          "cancerType": "Liver Cancer",
          "setid": "7__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "28",
          "Workflow": "Oncomine Comprehensive DNA v3 - Fusion ST- 540 - w2.1- DNA and Fusions - Single Sample",
          "Gender": "Female",
          "nucleotideType": "DNA",
          "barcodeId": "IonXpress_011",
          "sample": "pgm-s11",
          "Relation": "DNA_RNA",
          "RelationRole": "Self",
          "setid": "8__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "29",
          "Workflow": "Oncomine Comprehensive DNA v3 - Fusion ST- 540 - w2.1- DNA and Fusions - Single Sample",
          "Gender": "Female",
          "nucleotideType": "RNA",
          "barcodeId": "IonXpress_012",
          "sample": "pgm-s12T",
          "Relation": "DNA_RNA",
          "RelationRole": "Self",
          "setid": "8__7179df4c-c6bb-4cbe-97a4-bb48951a4acd"
        },
        {
          "row": "30",
          "Workflow": "AmpliSeq Exome trio",
          "Gender": "Female",
          "barcodeId": "IonXpress_011",
          "sample": "pgm-s11",
          "Relation": "Trio",
          "RelationRole": "Mother",
          "NucleotideType": "DNA",
          "setid": "9__837663e7-f7f8-4334-b14b-dea091dd353b"
        },
        {
          "row": "31",
          "Workflow": "AmpliSeq Exome trio",
          "Gender": "Male",
          "barcodeId": "IonXpress_012",
          "sample": "pgm-s12T",
          "Relation": "Trio",
          "RelationRole": "Father",
          "NucleotideType": "DNA",
          "setid": "9__837663e7-f7f8-4334-b14b-dea091dd353b"
        },
        {
          "row": "32",
          "Workflow": "AmpliSeq Exome trio",
          "Gender": "Male",
          "barcodeId": "IonXpress_012",
          "sample": "pgm-s12N",
          "Relation": "Trio",
          "RelationRole": "Proband",
          "NucleotideType": "DNA",
          "setid": "9__837663e7-f7f8-4334-b14b-dea091dd353b"
        }
      ],
      "accountId":"planned_irAccount_id_blahblahblah",
      "accountName":"planned_irAccount_name_blahblahblah"
     }
    c["userInput"]=p

    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "get_plugin_dir() "
    #print get_plugin_dir()
    #print ""
    #print ""
    #print ""
    #print ""
    ##print ""
    #print "set_classpath() "
    #print set_classpath()
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "get range for number of parallel streams ========================="
    #print  getPermissibleRangeOfNumParallelStreamsValues(c)
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "get range for file segment size ========================="
    #print getPermissibleRangeOfFileSegmentSizeValues(c)
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    ##print "java command outputs for "
    #print get_httpResponseFromIRUJavaAsJson("-u ion.reporter@lifetech.com -w 123456 -p https -a think1.itw -x 443 -v 46 -o userDetails")
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "user details ==============================="
    #print getUserDetails(c)
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "config"
    #print c
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "cancer types"
    #print getIRCancerTypesList(c)
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "landing page"
    #print getWorkflowCreationLandingPageURL(c)
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "versions list ==============================="
    #print get_versions(c)
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print " workflow list"
    #print getWorkflowList(c)
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "user input table "
    print getUserInput(c)
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "validate user input"
    #print validateUserInput(c)
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "IR GUI url "
    #print getIRGUIBaseURL(c)
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "landing page"
    #print getWorkflowCreationLandingPageURL(c)
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "landing page base"
    #print getWorkflowCreationLandingPageURLBase(c)
    #print ""
    #print ""
    #print ""
    #print ""
    #print ""
    #print "user details 2"
    #print getUserDetails(d)
    #print ""
    #print ""
    #print ""




