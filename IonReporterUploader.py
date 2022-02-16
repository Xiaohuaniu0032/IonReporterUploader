#!/usr/bin/python
# Copyright (C) 2012 Ion Torrent Systems, Inc. All Rights Reserved
# vim: tabstop=4 shiftwidth=4 softtabstop=4 noexpandtab
# Ion Plugin - Ion Reporter Uploader

import getopt
import os
import sys
import json
import datetime
import time
import urllib
import urllib2
import subprocess
import ast
import shutil
import ConfigParser
import base64
import urlparse

import requests
from ion.plugin import *

import extend

#######
###  global variables 
pluginName = ""
plugin_dir = ""
javaHome="java/amazon-corretto-11.0.7.10.1-linux-x64"
#javaHome="java/jre/openjdk-7-jre-headless/usr/lib/jvm/java-7-openjdk-amd64/jre"
#javaHome="java/jre/java-7-openjdk-amd64/jre"
#javaHome="java/jre/openjdk-7-rpm/usr/lib/jvm/java-1.7.0-openjdk-1.7.0.85.x86_64/jre"
javaBinRelativePath=javaHome + "/bin" 
javaBin=""

class IonReporterUploader(IonPlugin):
    #Reading the IRU version information from the IRU.version file using the ConfigParser
    config = ConfigParser.RawConfigParser()
    config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'IRU.version'))
    version = config.get('global', 'version')
    
    runtypes = [RunType.THUMB, RunType.FULLCHIP, RunType.COMPOSITE]
    #runlevels = [RunLevel.PRE, RunLevel.BLOCK, RunLevel.POST]
    runlevels = [RunLevel.PRE, RunLevel.POST]
    features = [Feature.EXPORT]
    depends = ["variantCaller","sampleID", "coverageAnalysis", "molecularCoverageAnalysis"]

    #JIRA [TS-7563]
    allow_autorun = False

    global pluginName, plugin_dir, launchOption, commonScratchDir, javaBinRelativePath, javaBin, accountType
    pluginName = "IonReporterUploader"
    plugin_dir = os.getenv("RUNINFO__PLUGIN_DIR") or os.path.dirname(__file__)
    javaBinPath=plugin_dir + "/" + javaBinRelativePath
    javaBin=javaBinPath + "/" + "java"
    currentPath = os.getenv("PATH")
    newPath = javaBinPath +":" + currentPath
    accountType = "ir"
    print "PATH is " + newPath
    os.environ["PATH"] = newPath
    os.environ["JAVA_HOME"] = javaHome
    print "java is " + javaBin
    launchOption = "upload_and_launch"
    extend.setPluginName(pluginName)
    extend.setPluginDir(plugin_dir)

    #print "plugin dir is " + os.getenv("RUNINFO__PLUGIN_DIR")
    #print "plugin name is " + os.getenv("RUNINFO__PLUGIN_NAME")
    #print "plugin runtime key is " + os.getenv("RUNINFO__PK")

    def pre_launch(self):
        return True

    #Launches script with parameter jsonfilename. Assumes data is a dict
    def launch(self, data=None):
        global launchOption, commonScratchDir
        print pluginName + ".py launch()"
        startpluginjsonfile = os.getenv("RESULTS_DIR") + "/startplugin.json"
        print "input file is " + startpluginjsonfile
        data = open(startpluginjsonfile).read()
        commonScratchDir = self.get_commonScratchDir(data)
        runtype = self.get_runinfo("run_type", data)
        runlevel = self.get_runinfo("runlevel", data)
        print "RUN TYPE " + runtype
        print "RUN LEVEL " + runlevel
        dt = json.loads(data)
        pluginconfig = dt["pluginconfig"]
        if 'launchoption' in pluginconfig:
            launchOption = pluginconfig["launchoption"]
        print "LAUNCH OPTION " + launchOption
        self.write_classpath()

        self.process_status_lock(runlevel)

        if runtype == "composite" and runlevel == "pre":
            self.pre(data)
        #elif runtype == "composite" and runlevel == "block":
            #self.block(data)
        elif runtype == "composite" and runlevel == "post":
            print "POST IS CALLED"
            self.post(data)
        elif runtype == "wholechip" and runlevel == "default":  #PGM
            self.default(data)
        elif runtype == "wholechip" and runlevel == "post":  #PGM
            self.default(data)
        elif runtype == "wholechip" and runlevel == "genexusTransfer":  #PGM
            self.genexusTransfer(data)
        else:
            print "IonReporterUploader : Ignoring the above combination of runtype and runlevel."
            print "                      It is normal that this plugin ignores certain runtype / runlevel combinations, as they are not required."
            print "                      Please look into the log.txt generated in  other runlevels via the status.html link. "
            print "                      Exiting from this run level.. "


        ## zip up the entire logs and plugins results folder and provide as download through summary.html
        if (  (runlevel == "default") or (runlevel == "post") or (runlevel == "genexusTransfer") ):
            zipcmd="(cd " + commonScratchDir + "/..;zip --quiet -x IRU_logs.zip  -r "+ commonScratchDir +"/IRU_logs.zip `basename " +commonScratchDir +"`/*)"
            proc = subprocess.Popen(zipcmd, shell=True, stdout=subprocess.PIPE)
            (zipout, ziperr)= proc.communicate()
            zipexit = proc.returncode
            #print "zipcmd  = " + zipcmd +"\n"
            #print "zipout  = " + zipout +"\n"
            if ziperr : print "ziperr  = " + ziperr +"\n"
            print "zipexit = " + str(zipexit) +"\n"
            if (zipexit == 0):
                #sedcmd="sed -i /\<!--PLACEHOLDER__FORZIPDOWNLOAD--\>/c\Download\&nbsp\;\<a\ href=IRU_logs.zip\>IRU\ logs\<\/a\> "+commonScratchDir + "/summary.html"
                #sedcmd="sed -i /\<!--PLACEHOLDER__FORZIPDOWNLOAD--\>/c\Download\&nbsp\;\<a\ href=IRU_logs.zip\>IRU\ logs\<\/a\> "+commonScratchDir + "/post/iruDetails.json"
                sedcmd="sed -i -e 's!PLACEHOLDER__FORZIPDOWNLOAD!<a href=IRU_logs.zip>Download IRU logs</a>!g' "+commonScratchDir + "/post/iruDetails.json"
                #sedcmd="(cd " + commonScratchDir + ";sed -i summary.html"+ commonScratchDir +"/IRU_logs.sed `basename " +commonScratchDir +"`/blah/*)"
                proc = subprocess.Popen(sedcmd, shell=True, stdout=subprocess.PIPE)
                (sedout, sederr)= proc.communicate()
                sedexit = proc.returncode



        return True


    # Return list of columns you want the plugin table UI to show.
    # Columns will be displayed in the order listed.
    def barcodetable_columns(self):
        columns = [
            {
                "field": "selected",
                "editable": True
            },
            {
                "field": "barcode_name",
                "editable": False
            },
            {
                "field": "sample",
                "editable": False
            },
        ]
        return columns

    # Optional function to specify initial table data.
    # Input data is the same structure as in barcodes.json,
    #    it can be passed as is or modified or overwritten by the plugin.
    # Example below modifies some fields in the default data and returns it.
    def barcodetable_data(self, data, planconfig, globalconfig):
        for d in data:
            if d['sample']:
                d['selected'] = True
                d['files_BAM'] = True
                d['files_VCF'] = False

        return data



    #Run Mode: Pre - clear old JSON, set initial run timestamp, log version and start time
    def pre(self, data):
        global pluginName, launchOption, accountType
        self.clear_JSON()
        self.set_serial_number()

        self.copy_new_status_block()
        self.copy_resultsFile()
        timestamp = self.get_timestamp()
        file = open(commonScratchDir + "/timestamp.txt", "w+")
        file.write(timestamp)
        file.close()
        self.inc_submissionCounts()
        self.write_log("VERSION=1.2", data)
        self.write_log(timestamp + " " + pluginName, data)
        self.write_classpath()
        self.test_report(data)
        dt = json.loads(data)
        pluginconfig = dt["pluginconfig"]
        if 'account_type' in pluginconfig:
          accountType = pluginconfig["account_type"]
        #self.get_plugin_parameters(data)
        log_text = self.get_timestamp() + pluginName + " : executing the IonReporter Uploader Client -- - pre"
        #if launchOption == "upload_and_launch":
        #    os.system(
        #        javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.Launcher -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
        #            log_text, data) + " -o pre ||true")
        #elif launchOption == "upload_only":
        #    os.system(
        #        javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.LauncherForUploadOnly -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
        #            log_text, data) + " -o pre ||true")
        os.system(
                javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.Launcher -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
                    log_text, data) + " -c " + "'" + accountType + "'" + " -o pre ||true")
        os.system("sleep 2")
        return True

    #Run Mode: Block (Proton) - copy status_block.html, test report exists, log, initialize classpath and objects.json, run java code
    def block(self, data):
        global pluginName, launchOption
        self.copy_status_block(commonScratchDir)
        #self.test_report(data)
        log_text = self.get_timestamp() + pluginName + " : executing the IonReporter Uploader Client -- block"
        self.write_classpath()
        #self.get_plugin_parameters(data)
        #print "LAUNCH OPTION " + launchOption
        #if launchOption == "upload_and_launch":
        #    os.system(
        #        javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.Launcher -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
        #            log_text, data) + " -o block ||true")
        #elif launchOption == "upload_only":
        #    os.system(
        #        javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.LauncherForUploadOnly -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
        #            log_text, data) + " -o block ||true")
        os.system(
                javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.Launcher -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
                    log_text, data) + " -o block ||true")
        os.system("sleep 2")
        self.write_log(
            pluginName + " : executed the IonReporter Client ... Exit Code = " + `os.getenv("LAUNCHERCLIENTEXITCODE")`,
            data)
        print "Returning from Block"
        return True

    #Run Mode: Default (PGM)- copy status_block.html, test report exists, log, initialize classpath and objects.json, run java code
    def default(self, data):
        global pluginName, launchOption, accountType
        self.clear_JSON()
        self.set_serial_number()
        self.copy_new_status_block()
        self.copy_resultsFile()
        timestamp = self.get_timestamp()
        file = open(commonScratchDir + "/timestamp.txt", "w+")
        file.write(timestamp)
        file.close()
        self.inc_submissionCounts()
        self.write_log("VERSION=1.2", data)
        self.write_log(timestamp + " IonReporterUploader", data)
        if os.getenv("CHIP_LEVEL_ANALYSIS_PATH") :
            resultsDir = os.getenv("RESULTS_DIR")
            resultsDirPost = os.path.join(resultsDir,"post")
            os.mkdir(resultsDirPost)
            startpluginjsonfile = os.getenv("RESULTS_DIR") + "/startplugin.json"
            print "input file is " + startpluginjsonfile
            startpluginjsondata = json.load(open(startpluginjsonfile))

            startpluginjsondata['runinfo']['results_dir'] = str(os.getenv("RESULTS_DIR")) + "/post"
            with open(startpluginjsonfile, 'w') as outfile:
                json.dump(startpluginjsondata, outfile)

            self.copy_status_block(resultsDirPost)
        else :
            self.copy_status_block(commonScratchDir)
        self.test_report(data)
        log_text = self.get_timestamp() + pluginName + " : executing the IonReporter Uploader Client -- default"
        dt = json.loads(data)
        pluginconfig = dt["pluginconfig"]
        if 'account_type' in pluginconfig:
            accountType = pluginconfig["account_type"]
        #print "before calling classpath"
        self.write_classpath()
        #self.get_plugin_parameters(data)
        #print "LAUNCH OPTION " + launchOption
        #if launchOption == "upload_and_launch":
        #    os.system(
        #        javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.Launcher -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
        #            log_text, data) + " -o default")
        #elif launchOption == "upload_only":
        #    os.system(
        #        javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.LauncherForUploadOnly -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
        #            log_text, data) + " -o default")
        self.write_log(accountType + ":accountType", data)
        os.system(
                javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.Launcher -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
                    log_text, data) + " -o default -c " + "'" + accountType + "'")
        os.system("sleep 2")
        return True

    #Run Mode: genexusTransfer (PGM)- copy status_block.html, test report exists, log, initialize classpath and objects.json, run java code
    def genexusTransfer(self, data):
        global pluginName, launchOption, accountType
        self.clear_JSON()
        self.set_serial_number()
        self.copy_new_status_block()
        self.copy_resultsFile()
        timestamp = self.get_timestamp()
        file = open(commonScratchDir + "/timestamp.txt", "w+")
        file.write(timestamp)
        file.close()
        self.inc_submissionCounts()
        self.write_log("VERSION=1.2", data)
        self.write_log(timestamp + " IonReporterUploader", data)
        if os.getenv("CHIP_LEVEL_ANALYSIS_PATH") :
            resultsDir = os.getenv("RESULTS_DIR")
            resultsDirPost = os.path.join(resultsDir,"post")
            os.mkdir(resultsDirPost)
            startpluginjsonfile = os.getenv("RESULTS_DIR") + "/startplugin.json"
            print "input file is " + startpluginjsonfile
            startpluginjsondata = json.load(open(startpluginjsonfile))

            startpluginjsondata['runinfo']['results_dir'] = str(os.getenv("RESULTS_DIR")) + "/post"
            with open(startpluginjsonfile, 'w') as outfile:
                json.dump(startpluginjsondata, outfile)

            self.copy_status_block(resultsDirPost)
        else :
            self.copy_status_block(commonScratchDir)
        self.test_report(data)
        log_text = self.get_timestamp() + pluginName + " : executing the IonReporter Uploader Client -- default"
        dt = json.loads(data)
        pluginconfig = dt["pluginconfig"]
        if 'account_type' in pluginconfig:
            accountType = pluginconfig["account_type"]
            #print "before calling classpath"
        self.write_classpath()
            #self.get_plugin_parameters(data)
            #print "LAUNCH OPTION " + launchOption
            #if launchOption == "upload_and_launch":
            #    os.system(
            #        javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.Launcher -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
            #            log_text, data) + " -o default")
            #elif launchOption == "upload_only":
            #    os.system(
            #        javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.LauncherForUploadOnly -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
            #            log_text, data) + " -o default")
        self.write_log(accountType + ":accountType", data)
        os.system(
                    javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.Launcher -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
                        log_text, data) + " -o genexusTransfer -c " + "'" + accountType + "'")
        os.system("sleep 2")
        return True

    # Run Mode: Post
    def post(self, data):
        global pluginName, launchOption, accountType
        self.write_classpath()
        self.copy_new_status_block()
        self.copy_resultsFile()
        self.test_report(data)
        log_text = self.get_timestamp() + pluginName + ": executing the IonReporter Uploader Client -- post"
        dt = json.loads(data)
        pluginconfig = dt["pluginconfig"]
        if 'account_type' in pluginconfig:
          accountType = pluginconfig["account_type"]
        #self.get_plugin_parameters(data)
        #print "LAUNCH OPTION " + launchOption
        #if launchOption == "upload_and_launch":
        #    os.system(
        #        javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.Launcher -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
        #            log_text, data) + " -o post  ||true")
        #elif launchOption == "upload_only":
        #    os.system(
        #        javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.LauncherForUploadOnly -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
        #            log_text, data) + " -o post  ||true")
        os.system(
                javaBin + " -Xms4g -Xmx4g -Djsse.enableSNIExtension=false -Dlog.home=${RESULTS_DIR} com.lifetechnologies.ionreporter.clients.irutorrentplugin.Launcher -j ${RESULTS_DIR}/startplugin.json -l " + self.write_log(
                    log_text, data) + " -c " + "'" + accountType + "'" + " -o post  ||true")
        os.system("sleep 2")
        return True

    # Versions
    def get_versions(self):
        global pluginName
        self.write_classpath()
        api_url = os.getenv('RUNINFO__API_URL',
                            'http://localhost/rundb/api/') + "/v1/plugin/?format=json&name=" + pluginName + "&active=true"
        f = urllib2.urlopen(api_url)
        d = json.loads(f.read())
        objects = d["objects"]
        config = objects[0]["config"]
        return extend.get_versions({"irAccount": config})


    # Returns Sample Relationship Fields used in TS 3.0. First invokes java program to save workflows to JSON file. Then reads.
    def getUserInput(self):
        return {"status": "false", "error": ""}
        global pluginName
        self.write_classpath()
        api_url = os.getenv('RUNINFO__API_URL',
                            'http://localhost/rundb/api/') + "/v1/plugin/?format=json&name=" + pluginName + "&active=true"
        f = urllib2.urlopen(api_url)
        d = json.loads(f.read())
        objects = d["objects"]
        if not objects:
            return None
        config = objects[0]["config"]

        #return extend.getUserInput({"irAccount":config})

    #return extend.get_versions({"irAccount":config})
    #return extend.authCheck({"irAccount":config})
    #return extend.getWorkflowList({"irAccount":config})
    #return extend.getUserDataUploadPath({"irAccount":config})
    #return extend.sampleExistsOnIR({"sampleName":"Sample_100","irAccount":config})        # always returning false?
    #return extend.getUserDetails({"userid":"vipinchandran_n@persistent.co.in","password":"123456","irAccount":config})
    #return extend.validateUserInput({"userInput":{},"irAccount":config})
    #return extend.getWorkflowCreationLandingPageURL({"irAccount":config})


    def get_commonScratchDir(self, data):
        d = json.loads(data)
        runinfo = d["runinfo"]
        runinfoPlugin = runinfo["plugin"]
        return runinfoPlugin["results_dir"]

    # increment the submission counts   # not thread safe, TBD.
    def inc_submissionCounts(self):
        newCount = 1
        line = ""
        #if os.path.exists(os.getenv("RESULTS_DIR") + "/submissionCount.txt"):
        if os.path.exists(commonScratchDir + "/submissionCount.txt"):
            submissionfile = open(commonScratchDir + "/submissionCount.txt")
            line = submissionfile.readline()
            submissionfile.close()
        if line != "":
            newCount = newCount + int(line)
        submissionfileWriter = open(commonScratchDir + "/submissionCount.txt", "w")
        submissionfileWriter.write(str(newCount))
        submissionfileWriter.close()
        return newCount

    # Returns timestamp from system
    def get_timestamp(self):
        now = datetime.datetime.now()
        timeStamp = `now.year` + "-" + `now.month` + "-" + `now.day` + "_" + `now.hour` + "_" + `now.minute` + "_" + `now.second`
        return timeStamp

    # Returns values (thru keys) from run_info json file
    def get_runinfo(self, key, data):
        d = json.loads(data)
        runinfo = d["runinfo"]
        if (key == "runlevel"):
            plugin = d["runplugin"]
            value = plugin[key]
            return value
        elif (key == "run_type"):
            plugin = d["runplugin"]
            value = plugin[key]
            return value
        value = runinfo[key]
        return value

    # Defines classpath
    def write_classpath(self):
        global pluginName
        # do not print anything to the standard out here .. the api calls use this, and gets messed up.
        #sub1 = subprocess.Popen("find /results/plugins/" + pluginName + "/ |grep \"\.jar$\" |xargs |sed 's/ /:/g'", shell=True, stdout=subprocess.PIPE)
        sub1 = subprocess.Popen("find " + plugin_dir + "/ |grep \"\.jar$\" |xargs |sed 's/ /:/g'", shell=True,
                                stdout=subprocess.PIPE)
        #classpath_str = os.getenv("RUNINFO__PLUGIN_DIR") + "/lib/java/shared:" + sub1.stdout.read().strip()
        classpath_str = plugin_dir + "/lib/java/shared:" + sub1.stdout.read().strip()
        os.environ["CLASSPATH"] = classpath_str
        if (os.getenv("LD_LIBRARY_PATH")):
            ld_str = plugin_dir + "/lib:" + os.getenv("LD_LIBRARY_PATH")
        else:
            ld_str = plugin_dir + "/lib"
            os.environ["LD_LIBRARY_PATH"] = ld_str

    # Tests if report exists
    def test_report(self, data):
        analysis_dir = self.get_runinfo("analysis_dir", data)
        report_file=analysis_dir + "/report.pdf"
        if os.path.isfile(report_file):
            return
        results_dir = self.get_runinfo("results_dir", data)
        report_file=results_dir + "/report.pdf"
        if os.path.isfile(report_file):
            return
        pk = self.get_runinfo("pk", data)
        api_url = self.get_runinfo("api_url", data)
        api_key = self.get_runinfo("api_key", data)
        pluginresult = self.get_runinfo("pluginresult", data)
        url = urlparse.urljoin(api_url, '/rundb/api/v1/results/%s/report/' % pk)
        params = {
            "api_key": api_key,
            "pluginresult": pluginresult
        }
        try:
            response = requests.get(url, params=params);
            report = open(report_file, "wb")
            report.write(response.content)
            report.close()
        except IOError:
            self.write_log("Report Generation (report.pdf) failed", data)


            # Create objects.json file (plugin parameters) thru RESTful

    def get_plugin_parameters(self, data):
        global pluginName
        api_url = self.get_runinfo("api_url", data) + "/v1/plugin/?format=json&name=" + pluginName + "&active=true"
        results_dir = self.get_runinfo("results_dir", data) + "/objects.json"
        urllib.urlretrieve(api_url, results_dir)

        #Check if new file exists
        if not os.path.isfile(results_dir):
            api_url = os.getenv('RUNINFO__API_URL',
                                'http://localhost/rundb/api/') + "/v1/plugin/?format=json&name=" + pluginName + "&active=true"
            urllib.urlretrieve(api_url, results_dir)
            if not os.path.isfile(results_dir):
                self.write_log("ERROR getting objects from database", data)
                sys.exit()

    # Writes to directory log file
    def write_log(self, text, data):
        log_file = self.get_runinfo("results_dir", data) + "/log.txt"
        file = open(log_file, "a")
        file.write(text)
        file.write("\n")
        return log_file

    #Clear JSON file to initial state (0%)
    def clear_JSON(self):
        if os.path.exists(os.getenv("RESULTS_DIR") + "./progress.json"):
            prog = open("progress.json", "w")
            prog.write("{ \"progress\": \"0\", \"status\": \"Started\", \"channels\" :[]  }")
        return True

    def set_serial_number(self):
        paramsJsonFilePath = os.getenv("ANALYSIS_DIR") + "/ion_params_00.json"
        paramsJsonFile = open(paramsJsonFilePath)
        paramsJsonData = json.load(paramsJsonFile)
        paramsJsonFile.close()

        paramsExpJson = paramsJsonData["exp_json"]
        if not isinstance(paramsExpJson, dict):
            paramsExpJson = json.loads(paramsJsonData["exp_json"])
        paramsExpJsonLog = paramsExpJson["log"]
        if not isinstance(paramsExpJsonLog, dict):
            paramsExpJsonLog = json.loads(paramsExpJson["log"])
        serialNum = paramsExpJsonLog["serial_number"]

        serialFile = open(commonScratchDir + "/serial.txt", "w")
        serialFile.write(serialNum)
        serialFile.close()

    def set_serial_number_old_depricated(self):
        sub1 = subprocess.Popen("cat " + os.getenv("ANALYSIS_DIR") + "/ion_params_00.json", shell=True,
                                stdout=subprocess.PIPE)
        word = sub1.stdout.read().strip()
        first_index = word.find("serial_number") + 22
        word2 = word[first_index:]
        end_index = word2.find("\\")
        serial_number = word2[:end_index]
        #block = open(os.getenv("RESULTS_DIR") + "/serial.txt", "w")
        block = open(commonScratchDir + "/serial.txt", "w")
        block.write(serial_number)

    def copy_status_block(self, resultsDir):
        shutil.copyfile(os.getenv("RUNINFO__PLUGIN_DIR") + "/status_block.html",
                        resultsDir + "/progress.html")

    def copy_new_status_block(self):
        """Copy the new_status_block.html static file into the plugin result's
        root directory.
        """
        source_path = os.path.join(os.getenv("RUNINFO__PLUGIN_DIR") , "new_status_block.html")
        destination_path = os.path.join(commonScratchDir, "new_status_block.html")
        if not os.path.exists(destination_path):
            shutil.copyfile(source_path, destination_path)

    def copy_resultsFile(self):
        """Copy the resultsFile.html static file into the plugin result's
        root directory.
        """
        source_path = os.path.join(os.getenv("RUNINFO__PLUGIN_DIR") , "resultsFile.html")
        folderPath = os.path.join(commonScratchDir, "results")
        if not os.path.exists(folderPath):
            os.makedirs(folderPath)
        destination_path = os.path.join(folderPath, "resultsFile.html")
        if not os.path.exists(destination_path):
            shutil.copyfile(source_path, destination_path)

    def process_status_lock(self, runlevel):
        # handles lock for instance.html page to determine whether plugin instance is in-progress
        results_dir = os.getenv("RESULTS_DIR")
        lockfile = 'iru_status.lock'
        if runlevel == 'pre':
            lockpath = os.path.join(results_dir,'post',lockfile)
            if os.path.exists(lockpath):
                print 'Removing status lock %s' % lockpath
                os.remove(lockpath)
        elif runlevel == 'post':
            lockpath = os.path.join(results_dir,lockfile)
            if not os.path.exists(lockpath):
                print 'Creating status lock %s' % lockpath
                open(lockpath, 'w').close()
            else:
                print 'Warning: status lock exists %s' % lockpath


if __name__ == "__main__": PluginCLI()
'''
if __name__=="__main__":
  ## test code for plugin api calls
	iru = IonReporterUploader();
	print ""
	print ""
	print "getversions output = " + iru.get_versions()
	print ""
	print ""
	print ""
	print "getUserInput output = " 
	print iru.getUserInput()
	print ""
	print ""
	print "inc_submissionCount output = " 
	print iru.inc_submissionCounts()
	print ""
	print ""
'''
