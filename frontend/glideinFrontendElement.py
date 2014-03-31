#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This is the main of the glideinFrontend
#
# Arguments:
#   $1 = parent PID
#   $2 = work dir
#   $3 = group_name
#
# Author:
#   Igor Sfiligoi (was glideinFrontend.py until Nov 21, 2008)
#

import signal
import sys
import os
import copy
import traceback
import time
import string
import logging
import cPickle
import re

sys.path.append(os.path.join(sys.path[0],"../.."))

from glideinwms.lib import symCrypto,pubCrypto
from glideinwms.lib import glideinWMSVersion
from glideinwms.lib import logSupport
from glideinwms.lib import cleanupSupport
from glideinwms.lib.fork import fork_in_bg
from glideinwms.lib.fork import register_sighandler

from glideinwms.frontend import glideinFrontendConfig
from glideinwms.frontend import glideinFrontendInterface
from glideinwms.frontend import glideinFrontendLib
from glideinwms.frontend import glideinFrontendPidLib
from glideinwms.frontend import glideinFrontendMonitoring
from glideinwms.frontend import glideinFrontendPlugins

class glideinFrontendElement:
    def __init__(self, parent_pid, work_dir, group_name):
        self.parent_pid = parent_pid
        self.work_dir = work_dir
        self.group_name = group_name

        self.elementDescript = glideinFrontendConfig.ElementMergedDescript(self.work_dir, self.group_name)
        self.paramsDescript = glideinFrontendConfig.ParamsDescript(self.work_dir, self.group_name)
        self.signatureDescript = glideinFrontendConfig.GroupSignatureDescript(self.work_dir, self.group_name)
        self.attr_dict = glideinFrontendConfig.AttrsDescript(self.work_dir,self.group_name).data
        self.startup_time = time.time()

        self.sleep_time = int(self.elementDescript.frontend_data['LoopDelay'])
        self.frontend_name = self.elementDescript.frontend_data['FrontendName']
        self.web_url = self.elementDescript.frontend_data['WebURL']
        self.monitoring_web_url = self.elementDescript.frontend_data['MonitoringWebURL']

        self.security_name = self.elementDescript.merged_data['SecurityName']
        self.factory_pools = self.elementDescript.merged_data['FactoryCollectors']

        self.max_running = int(self.elementDescript.element_data['MaxRunningPerEntry'])
        self.fraction_running = float(self.elementDescript.element_data['FracRunningPerEntry'])
        self.max_idle = int(self.elementDescript.element_data['MaxIdlePerEntry'])
        self.reserve_idle = int(self.elementDescript.element_data['ReserveIdlePerEntry'])
        self.max_vms_idle = int(self.elementDescript.element_data['MaxIdleVMsPerEntry'])
        self.curb_vms_idle = int(self.elementDescript.element_data['CurbIdleVMsPerEntry'])
        self.total_max_glideins=int(self.elementDescript.element_data['MaxRunningTotal'])
        self.total_curb_glideins=int(self.elementDescript.element_data['CurbRunningTotal'])
        self.total_max_vms_idle = int(self.elementDescript.element_data['MaxIdleVMsTotal'])
        self.total_curb_vms_idle = int(self.elementDescript.element_data['CurbIdleVMsTotal'])
        self.fe_total_max_glideins=int(self.elementDescript.frontend_data['MaxRunningTotal'])
        self.fe_total_curb_glideins=int(self.elementDescript.frontend_data['CurbRunningTotal'])
        self.fe_total_max_vms_idle = int(self.elementDescript.frontend_data['MaxIdleVMsTotal'])
        self.fe_total_curb_vms_idle = int(self.elementDescript.frontend_data['CurbIdleVMsTotal'])
        self.global_total_max_glideins=int(self.elementDescript.frontend_data['MaxRunningTotalGlobal'])
        self.global_total_curb_glideins=int(self.elementDescript.frontend_data['CurbRunningTotalGlobal'])
        self.global_total_max_vms_idle = int(self.elementDescript.frontend_data['MaxIdleVMsTotalGlobal'])
        self.global_total_curb_vms_idle = int(self.elementDescript.frontend_data['CurbIdleVMsTotalGlobal'])
        # Default bahavior: Use factory proxies unless configure overrides it
        self.x509_proxy_plugin = None

    def configure(self):
        ''' Do some initial configuration of the element. '''

        # the log dir is shared between the frontend main and the groups, so use a subdir
        logSupport.log_dir = os.path.join(self.elementDescript.frontend_data['LogDir'], "group_%s" % self.group_name)

        # Configure frontend group process logging
        process_logs = eval(self.elementDescript.frontend_data['ProcessLogs'])
        for plog in process_logs:
            logSupport.add_processlog_handler(self.group_name,
                                              logSupport.log_dir,
                                              plog['msg_types'],
                                              plog['extension'],
                                              int(float(plog['max_days'])),
                                              int(float(plog['min_days'])),
                                              int(float(plog['max_mbytes'])))
        logSupport.log = logging.getLogger(self.group_name)
        logSupport.log.info("Logging initialized")
        logSupport.log.debug("Frontend Element startup time: %s" % str(self.startup_time))

        glideinFrontendMonitoring.monitoringConfig.monitor_dir = os.path.join(self.work_dir, "monitor/group_%s" % self.group_name)
        glideinFrontendInterface.frontendConfig.advertise_use_tcp = (self.elementDescript.frontend_data['AdvertiseWithTCP'] in ('True', '1'))
        glideinFrontendInterface.frontendConfig.advertise_use_multi = (self.elementDescript.frontend_data['AdvertiseWithMultiple'] in ('True', '1'))

        try:
            glideinwms_dir = os.path.dirname(os.path.dirname(sys.argv[0]))
            glideinFrontendInterface.frontendConfig.glideinwms_version = glideinWMSVersion.GlideinWMSDistro(glideinwms_dir, 'checksum.frontend').version()
        except:
            logSupport.log.exception("Exception occurred while trying to retrieve the glideinwms version: ")

        if self.elementDescript.merged_data['Proxies']:
            proxy_plugins = glideinFrontendPlugins.proxy_plugins
            if not proxy_plugins.get(self.elementDescript.merged_data['ProxySelectionPlugin']):
                logSupport.log.warning("Invalid ProxySelectionPlugin '%s', supported plugins are %s" % (
                    self.elementDescript.merged_data['ProxySelectionPlugin']),
                    proxy_plugins.keys())
                return 1
            self.x509_proxy_plugin = proxy_plugins[self.elementDescript.merged_data['ProxySelectionPlugin']](
                os.path.join(self.work_dir, "group_%s" % self.group_name),
                glideinFrontendPlugins.createCredentialList(self.elementDescript))

        # set the condor configuration and GSI setup globally, so I don't need to worry about it later on
        os.environ['CONDOR_CONFIG'] = self.elementDescript.frontend_data['CondorConfig']
        os.environ['_CONDOR_CERTIFICATE_MAPFILE'] = self.elementDescript.element_data['MapFile']
        os.environ['X509_USER_PROXY'] = self.elementDescript.frontend_data['ClassAdProxy']


    def main(self):
        self.configure()
        # create lock file
        pid_obj = glideinFrontendPidLib.ElementPidSupport(self.work_dir,
                                                          self.group_name)
        pid_obj.register(self.parent_pid)
        try:
            try:
                logSupport.log.info("Starting up")
                self.iterate()
            except KeyboardInterrupt:
                logSupport.log.info("Received signal...exit")
            except:
                logSupport.log.exception("Unhandled exception, dying: ")
        finally:
            pid_obj.relinquish()


    def iterate(self):
        self.stats = {}
        self.history_obj = {}

        if not self.elementDescript.frontend_data.has_key('X509Proxy'):
            self.published_frontend_name = '%s.%s' % (self.frontend_name,
                                                      self.group_name)
        else:
            # if using a VO proxy, label it as such
            # this way we don't risk of using the wrong proxy on the other side
            # if/when we decide to stop using the proxy
            self.published_frontend_name = '%s.XPVO_%s' % (self.frontend_name,
                                                           self.group_name)

        try:
            is_first = 1
            while 1: # will exit by exception
                check_parent(self.parent_pid)
                logSupport.log.info("Iteration at %s" % time.ctime())
                try:
                    # recreate every time to start from a clean state
                    self.stats['group'] = glideinFrontendMonitoring.groupStats()

                    done_something = self.iterate_one()
                    logSupport.log.info("iterate_one status: %s" % str(done_something))

                    logSupport.log.info("Writing stats")
                    try:
                        write_stats(self.stats)
                    except KeyboardInterrupt:
                        raise # this is an exit signal, pass through
                    except:
                        # never fail for stats reasons!
                        logSupport.log.exception("Exception occurred writing stats: " )
                except KeyboardInterrupt:
                    raise # this is an exit signal, pass trough
                except:
                    if is_first:
                        raise
                    else:
                        # if not the first pass, just warn
                        logSupport.log.exception("Exception occurred iteration: ")
                is_first = 0

                # do it just before the sleep
                cleanupSupport.cleaners.cleanup()

                logSupport.log.info("Sleeping %s sec" % self.sleep_time)
                time.sleep(self.sleep_time)
        finally:
            logSupport.log.info("Deadvertize my ads")
            self.deadvertiseAllClassads()


    def deadvertiseAllClassads(self):
        # Invalidate all glideclient glideclientglobal classads
        for factory_pool in self.factory_pools:
            factory_pool_node = factory_pool[0]
            try:
                glideinFrontendInterface.deadvertizeAllWork(factory_pool_node, self.published_frontend_name)
            except:
                # Ignore errors
                pass

            try:
                glideinFrontendInterface.deadvertizeAllGlobals(factory_pool_node, self.published_frontend_name)
            except:
                # Ignore errors
                pass

        # Invalidate all glideresource classads
        try:
            resource_advertiser = glideinFrontendInterface.ResourceClassadAdvertiser()
            resource_advertiser.invalidateConstrainedClassads('GlideClientName == "%s"' % self.published_frontend_name)
        except:
            # Ignore all errors
            pass


    def iterate_one(self):
        pipe_ids={}

        logSupport.log.info("Querying schedd, entry, and glidein status using child processes.")

        # query globals
        pipe_ids['globals'] = fork_in_bg(self.query_globals)

        # query entries
        pipe_ids['entries'] = fork_in_bg(self.query_entries)

        ## schedd
        pipe_ids['jobs'] = fork_in_bg(self.get_condor_q)

        ## resource
        pipe_ids['startds'] = fork_in_bg(self.get_condor_status)

        try:
            pipe_out=fetch_fork_result_list(pipe_ids)
        except RuntimeError, e:
            # expect all errors logged already
            logSupport.log.info("Missing schedd, factory entry, and/or current glidein state information. " \
                                "Unable to calculate required glideins, terminating loop.")
            return
        logSupport.log.info("All children terminated")

        self.globals_dict = pipe_out['globals']
        self.glidein_dict=pipe_out['entries']
        self.condorq_dict = pipe_out['jobs']
        (self.status_dict,self.fe_counts,self.global_counts)=pipe_out['startds']

        # M2Crypto objects are not picklable, so do the transforamtion here
        self.populate_pubkey()
        self.populate_condorq_dict_types()

        condorq_dict_types = self.condorq_dict_types
        condorq_dict_abs = glideinFrontendLib.countCondorQ(self.condorq_dict)

        self.stats['group'].logJobs(
            {'Total':condorq_dict_abs,
             'Idle':condorq_dict_types['Idle']['abs'],
             'OldIdle':condorq_dict_types['OldIdle']['abs'],
             'Running':condorq_dict_types['Running']['abs']})

        logSupport.log.info("Jobs found total %i idle %i (old %i, grid %i, voms %i) running %i" % (condorq_dict_abs,
                   condorq_dict_types['Idle']['abs'],
                   condorq_dict_types['OldIdle']['abs'],
                   condorq_dict_types['ProxyIdle']['abs'],
                   condorq_dict_types['VomsIdle']['abs'],
                   condorq_dict_types['Running']['abs']))

        self.populate_status_dict_types()
        glideinFrontendLib.appendRealRunning(self.condorq_dict_running,
                                             self.status_dict_types['Running']['dict'])

        self.stats['group'].logGlideins(
            {'Total':self.status_dict_types['Total']['abs'],
             'Idle':self.status_dict_types['Idle']['abs'],
             'Running':self.status_dict_types['Running']['abs']})

        total_glideins=self.status_dict_types['Total']['abs']
        total_running_glideins=self.status_dict_types['Running']['abs']
        total_idle_glideins=self.status_dict_types['Idle']['abs']

        logSupport.log.info("Group glideins found total %i limit %i curb %i; of these idle %i limit %i curb %i running %i"%
                            (total_glideins,self.total_max_glideins,self.total_curb_glideins,
                             total_idle_glideins,self.total_max_vms_idle,self.total_curb_vms_idle,
                             total_running_glideins)
                            )
        
        fe_total_glideins=self.fe_counts['Total']
        fe_total_idle_glideins=self.fe_counts['Idle']
        logSupport.log.info("Frontend glideins found total %i limit %i curb %i; of these idle %i limit %i curb %i"%
                            (fe_total_glideins,self.fe_total_max_glideins,self.fe_total_curb_glideins,
                             fe_total_idle_glideins,self.fe_total_max_vms_idle,self.fe_total_curb_vms_idle)
                            )
        
        
        global_total_glideins=self.global_counts['Total']
        global_total_idle_glideins=self.global_counts['Idle']
        logSupport.log.info("Overall slots found total %i limit %i curb %i; of these idle %i limit %i curb %i"%
                            (global_total_glideins,self.global_total_max_glideins,self.global_total_curb_glideins,
                             global_total_idle_glideins,self.global_total_max_vms_idle,self.global_total_curb_vms_idle)
                            )

        # Update x509 user map and give proxy plugin a chance
        # to update based on condor stats
        if self.x509_proxy_plugin:
            logSupport.log.info("Updating usermap ");
            self.x509_proxy_plugin.update_usermap(self.condorq_dict,
                                                  condorq_dict_types,
                                                  self.status_dict,
                                                  self.status_dict_types)

        # here we have all the data needed to build a GroupAdvertizeType object
        descript_obj = glideinFrontendInterface.FrontendDescript(
                           self.published_frontend_name,
                           self.frontend_name,
                           self.group_name,
                           self.web_url,
                           self.signatureDescript.frontend_descript_fname,
                           self.signatureDescript.group_descript_fname,
                           self.signatureDescript.signature_type,
                           self.signatureDescript.frontend_descript_signature,
                           self.signatureDescript.group_descript_signature,
                           self.x509_proxy_plugin)
        descript_obj.add_monitoring_url(self.monitoring_web_url)

        # reuse between loops might be a good idea, but this will work for now
        key_builder = glideinFrontendInterface.Key4AdvertizeBuilder()

        logSupport.log.info("Match")

        # extract only the attribute names from format list
        self.condorq_match_list = [f[0] for f in self.elementDescript.merged_data['JobMatchAttrs']]

        #logSupport.log.debug("realcount: %s\n\n" % glideinFrontendLib.countRealRunning(elementDescript.merged_data['MatchExprCompiledObj'],condorq_dict_running,glidein_dict))

        self.do_match()

        logSupport.log.info("Total matching idle %i (old %i) running %i limit %i" % (condorq_dict_types['Idle']['total'],
     condorq_dict_types['OldIdle']['total'],
     self.condorq_dict_types['Running']['total'],
     self.max_running))

        advertizer = glideinFrontendInterface.MultiAdvertizeWork(descript_obj)
        resource_advertiser = glideinFrontendInterface.ResourceClassadAdvertiser(multi_support=glideinFrontendInterface.frontendConfig.advertise_use_multi)

        # Add globals
        for globalid, globals_el in self.globals_dict.iteritems():
            if globals_el['attrs'].has_key('PubKeyObj'):
                key_obj = key_builder.get_key_obj(
                              globals_el['attrs']['FactoryPoolId'],
                              globals_el['attrs']['PubKeyID'],
                              globals_el['attrs']['PubKeyObj'])
                advertizer.add_global(globals_el['attrs']['FactoryPoolNode'],
                                      globalid, self.security_name, key_obj)


        glideid_list = condorq_dict_types['Idle']['count'].keys()
        # TODO: PM Following shows up in branch_v2plus. Which is correct?
        # glideid_list=glidein_dict.keys()
        # sort for the sake of monitoring
        glideid_list.sort()

        # we will need this for faster lookup later
        self.processed_glideid_strs=[]

        log_factory_header()
        total_up_stats_arr=init_factory_stats_arr()
        total_down_stats_arr=init_factory_stats_arr()
        for glideid in glideid_list:
            if glideid == (None, None, None):
                continue # This is the special "Unmatched" entry
            factory_pool_node = glideid[0]
            request_name = glideid[1]
            my_identity = str(glideid[2]) # get rid of unicode
            glideid_str = "%s@%s" % (request_name, factory_pool_node)
            self.processed_glideid_strs.append(glideid_str)

            glidein_el = self.glidein_dict[glideid]
            glidein_in_downtime = \
                glidein_el['attrs'].get('GLIDEIN_In_Downtime') == 'True'

            count_jobs={}     # straight match
            prop_jobs={}      # proportional subset for this entry
            hereonly_jobs={}  # can only run on this site
            for dt in condorq_dict_types.keys():
                count_jobs[dt] = condorq_dict_types[dt]['count'][glideid]
                prop_jobs[dt] = condorq_dict_types[dt]['prop'][glideid]
                hereonly_jobs[dt] = condorq_dict_types[dt]['hereonly'][glideid]

            count_status=self.count_status_multi[request_name]

            #If the glidein requires a voms proxy, only match voms idle jobs
            # Note: if GLEXEC is set to NEVER, the site will never see the proxy, 
            # so it can be avoided.
            if (self.glexec != 'NEVER'):
                if (glidein_el['attrs'].get('GLIDEIN_REQUIRE_VOMS')=="True"):
                        prop_jobs['Idle']=prop_jobs['VomsIdle']
                        logSupport.log.info("Voms proxy required, limiting idle glideins to: %i" % prop_jobs['Idle'])
                elif (glidein_el['attrs'].get('GLIDEIN_REQUIRE_GLEXEC_USE')=="True"):
                        prop_jobs['Idle']=prop_jobs['ProxyIdle']
                        logSupport.log.info("Proxy required (GLEXEC), limiting idle glideins to: %i" % prop_jobs['Idle'])


            # effective idle is how much more we need
            # if there are idle slots, subtract them, they should match soon
            effective_idle = max(prop_jobs['Idle'] - count_status['Idle'], 0)
            effective_oldidle = max(prop_jobs['OldIdle']-count_status['Idle'], 0)

            glidein_min_idle = self.compute_glidein_min_idle(
                                   count_status, total_glideins, total_idle_glideins,
                                   fe_total_glideins, fe_total_idle_glideins,
                                   global_total_glideins, global_total_idle_glideins,
                                   effective_idle, effective_oldidle)

            glidein_max_run = self.compute_glidein_max_run(
                                  prop_jobs, self.count_real[glideid])

            remove_excess_str = self.choose_remove_excess_type(
                                    count_jobs, count_status, glideid)

            this_stats_arr = (prop_jobs['Idle'], count_jobs['Idle'],
                              effective_idle, prop_jobs['OldIdle'],
                              hereonly_jobs['Idle'], count_jobs['Running'],
                              self.count_real[glideid], self.max_running,
                              count_status['Total'], count_status['Idle'],
                              count_status['Running'],
                              glidein_min_idle, glidein_max_run)

            self.stats['group'].logMatchedJobs(
                glideid_str, prop_jobs['Idle'], effective_idle,
                prop_jobs['OldIdle'], count_jobs['Running'], self.count_real[glideid])

            self.stats['group'].logMatchedGlideins(
                glideid_str, count_status['Total'], count_status['Idle'],
                count_status['Running'])

            self.stats['group'].logFactAttrs(glideid_str, glidein_el['attrs'],
                                             ('PubKeyValue', 'PubKeyObj'))

            self.stats['group'].logFactDown(glideid_str, glidein_in_downtime)

            if glidein_in_downtime:
                total_down_stats_arr = log_and_sum_factory_line(
                                           glideid_str, glidein_in_downtime,
                                           this_stats_arr, total_down_stats_arr)
            else:
                total_up_stats_arr = log_and_sum_factory_line(
                                         glideid_str, glidein_in_downtime,
                                         this_stats_arr, total_up_stats_arr)

            # get the parameters
            glidein_params = copy.deepcopy(self.paramsDescript.const_data)
            for k in self.paramsDescript.expr_data.keys():
                kexpr = self.paramsDescript.expr_objs[k]
                # convert kexpr -> kval
                glidein_params[k] = glideinFrontendLib.evalParamExpr(kexpr, self.paramsDescript.const_data, glidein_el)
            # we will need this param to monitor orphaned glideins
            glidein_params['GLIDECLIENT_ReqNode'] = factory_pool_node

            self.stats['group'].logFactReq(
                glideid_str, glidein_min_idle, glidein_max_run, glidein_params)

            glidein_monitors = {}
            for t in count_jobs.keys():
                glidein_monitors[t] = count_jobs[t]

            glidein_monitors['RunningHere'] = self.count_real[glideid]

            for t in count_status.keys():
                glidein_monitors['Glideins%s' % t] = count_status[t]

            key_obj = None
            for globalid in self.globals_dict:
                if glideid[1].endswith(globalid):
                    globals_el = self.globals_dict[globalid]
                    if (globals_el['attrs'].has_key('PubKeyObj') and globals_el['attrs'].has_key('PubKeyID')):
                        key_obj = key_builder.get_key_obj(my_identity, globals_el['attrs']['PubKeyID'], globals_el['attrs']['PubKeyObj'])
                    break            

            trust_domain = glidein_el['attrs'].get('GLIDEIN_TrustDomain','Grid')
            auth_method = glidein_el['attrs'].get('GLIDEIN_SupportedAuthenticationMethod', 'grid_proxy')

            # Only advertize if there is a valid key for encryption
            if key_obj is not None:
                advertizer.add(factory_pool_node,
                               request_name, request_name,
                               glidein_min_idle, glidein_max_run,
                               glidein_params, glidein_monitors,
                               remove_excess_str=remove_excess_str,
                               key_obj=key_obj, glidein_params_to_encrypt=None,
                               security_name=self.security_name,
                               trust_domain=trust_domain,
                               auth_method=auth_method)
            else:
                logSupport.log.warning("Cannot advertise requests for %s because no factory %s key was found"% (request_name, factory_pool_node))


            resource_classad = self.build_resource_classad(
                                   this_stats_arr, request_name,
                                   glidein_el, glidein_in_downtime)
            resource_advertiser.addClassad(resource_classad.adParams['Name'],
                                           resource_classad)

        # end for glideid in condorq_dict_types['Idle']['count'].keys()

        total_down_stats_arr = self.count_factory_entries_without_classads(total_down_stats_arr)

        self.log_and_print_total_stats(total_up_stats_arr, total_down_stats_arr)
        self.log_and_print_unmatched(total_down_stats_arr)

        # Advertise glideclient and glideclient global classads
        try:
            logSupport.log.info("Advertising global requests")
            advertizer.do_global_advertize()
        except Exception:
            logSupport.log.exception("Unknown error advertising global requests")
        try:
            # cannot advertise len of queue since has both
            # glideclientglobal and glideclient
            logSupport.log.info("Advertising glidein requests")
            advertizer.do_advertize()
        except Exception:
            logSupport.log.exception("Unknown error advertising glidein requests")

        logSupport.log.info("Done advertising requests")

        # Advertise glideresource classads
        try:
            logSupport.log.info("Advertising %i glideresource classads to the user pool" %  len(resource_advertiser.classads))
            #logSupport.log.info("glideresource classads to advertise -\n%s" % resource_advertiser.getAllClassads())
            resource_advertiser.advertiseAllClassads()
            logSupport.log.info("Done advertising glideresource classads")
        except:
            logSupport.log.exception("Advertising failed: ")

        return

    def populate_pubkey(self):
        for globalid, globals_el in self.globals_dict.iteritems():
            try:
                globals_el['attrs']['PubKeyObj'] = pubCrypto.PubRSAKey(globals_el['attrs']['PubKeyValue'])
            except:
                # if no valid key
                # if key needed, will handle the error later on
                logSupport.log.warning("Factory Globals '%s': invalid RSA key" % globalid)
                logSupport.log.exception("Factory Globals '%s': invalid RSA key" % globalid)
                # but remove it also from the dictionary
                del self.globals_dict[globalid]

    def populate_condorq_dict_types(self):
        condorq_dict_proxy=glideinFrontendLib.getIdleProxyCondorQ(self.condorq_dict)
        condorq_dict_voms=glideinFrontendLib.getIdleVomsCondorQ(self.condorq_dict)
        condorq_dict_idle = glideinFrontendLib.getIdleCondorQ(self.condorq_dict)
        condorq_dict_old_idle = glideinFrontendLib.getOldCondorQ(condorq_dict_idle, 600)
        self.condorq_dict_running = glideinFrontendLib.getRunningCondorQ(self.condorq_dict)

        self.condorq_dict_types = {
            'Idle': {
                'dict':condorq_dict_idle,
                'abs':glideinFrontendLib.countCondorQ(condorq_dict_idle)
            },
            'OldIdle': {
                'dict':condorq_dict_old_idle,
                'abs':glideinFrontendLib.countCondorQ(condorq_dict_old_idle)
            },
            'VomsIdle': {
                'dict':condorq_dict_voms,
                'abs':glideinFrontendLib.countCondorQ(condorq_dict_voms)},
            'ProxyIdle': {
                'dict':condorq_dict_proxy,
                'abs':glideinFrontendLib.countCondorQ(condorq_dict_proxy)
            },
            'Running': {
                'dict':self.condorq_dict_running,
                'abs':glideinFrontendLib.countCondorQ(self.condorq_dict_running)
            }
        }

    def populate_status_dict_types(self):
        status_dict_idle = glideinFrontendLib.getIdleCondorStatus(self.status_dict)
        status_dict_running = glideinFrontendLib.getRunningCondorStatus(self.status_dict)

        self.status_dict_types = {
            'Total': {
                'dict':self.status_dict,
                'abs':glideinFrontendLib.countCondorStatus(self.status_dict)
            },
            'Idle': {
                'dict':status_dict_idle,
                'abs':glideinFrontendLib.countCondorStatus(status_dict_idle)
            },
            'Running': {
                'dict':status_dict_running,
                'abs':glideinFrontendLib.countCondorStatus(status_dict_running)
            }
        }

    def build_resource_classad(self, this_stats_arr, request_name, glidein_el, glidein_in_downtime):
        # Create the resource classad and populate the required information
        resource_classad = glideinFrontendInterface.ResourceClassad(request_name, self.published_frontend_name)
        resource_classad.setInDownTime(glidein_in_downtime)
        resource_classad.setEntryInfo(glidein_el['attrs'])
        resource_classad.setGlideFactoryMonitorInfo(glidein_el['monitor'])
        resource_classad.setMatchExprs(
            self.elementDescript.merged_data['MatchExpr'],
            self.elementDescript.merged_data['JobQueryExpr'],
            self.elementDescript.merged_data['FactoryQueryExpr'],
            self.attr_dict['GLIDECLIENT_Start'])
        try:
            resource_classad.setGlideClientMonitorInfo(this_stats_arr)
        except RuntimeError:
            logSupport.log.exception("Populating GlideClientMonitor info in resource classad failed: ")

        return resource_classad

    def compute_glidein_min_idle(self, count_status, total_glideins,
                                 total_idle_glideins, fe_total_glideins,
                                 fe_total_idle_glideins, global_total_glideins,
                                 global_total_idle_glideins,
                                 effective_idle, effective_oldidle):
        ''' Calculate the number of idle jobs to request from the factory '''

        if ( (count_status['Total'] >= self.max_running) or
             (count_status['Idle'] >= self.max_vms_idle) or
             (total_glideins >= self.total_max_glideins) or
             (total_idle_glideins >= self.total_max_vms_idle) or
             (fe_total_glideins >= self.fe_total_max_glideins) or
             (fe_total_idle_glideins >= self.fe_total_max_vms_idle) or
             (global_total_glideins >= self.global_total_max_glideins) or
             (global_total_idle_glideins>=self.global_total_max_vms_idle) ):

            # Do not request more glideins under following conditions:
            # 1. Have all the running jobs I wanted
            # 2. Have enough idle vms/slots
            # 3. Reached the system-wide limit
            glidein_min_idle=0
        elif (effective_idle>0):
            # don't go over the system-wide max
            # not perfect, given te number of entries, but better than nothing
            glidein_min_idle = min(
                effective_idle,
                self.max_running-count_status['Total'],
                self.total_max_glideins-total_glideins,
                self.total_max_vms_idle-total_idle_glideins,
                self.fe_total_max_glideins-fe_total_glideins,
                self.fe_total_max_vms_idle-fe_total_idle_glideins,
                self.global_total_max_glideins-global_total_glideins,
                self.global_total_max_vms_idle-global_total_idle_glideins)

            # since it takes a few cycles to stabilize, ask for only one third
            glidein_min_idle=glidein_min_idle/3
            # do not reserve any more than the number of old idles
            # for reserve (/3)
            glidein_idle_reserve = min(effective_oldidle/3, self.reserve_idle)

            glidein_min_idle+=glidein_idle_reserve
            glidein_min_idle = min(glidein_min_idle, self.max_idle)

            if count_status['Idle'] >= self.curb_vms_idle:
                glidein_min_idle/=2 # above first treshold, reduce
            if total_glideins >= self.total_curb_glideins:
                glidein_min_idle/=2 # above global treshold, reduce further
            if total_idle_glideins >= self.total_curb_vms_idle:
                glidein_min_idle/=2 # above global treshold, reduce further
            if fe_total_glideins>=self.fe_total_curb_glideins:
                glidein_min_idle/=2 # above global treshold, reduce further
            if fe_total_idle_glideins>=self.fe_total_curb_vms_idle:
                glidein_min_idle/=2 # above global treshold, reduce further
            if global_total_glideins>=self.global_total_curb_glideins:
                glidein_min_idle/=2 # above global treshold, reduce further
            if global_total_idle_glideins>=self.global_total_curb_vms_idle:
                glidein_min_idle/=2 # above global treshold, reduce further
            if glidein_min_idle<1:
                glidein_min_idle=1
        else:
            # no idle, make sure the glideins know it
            glidein_min_idle = 0

        return int(glidein_min_idle)

    def compute_glidein_max_run(self, prop_jobs, real):
        glidein_max_run = 0

        # we don't need more slots than number of jobs in the queue (unless the fraction is positive)
        if (prop_jobs['Idle'] + real) > 0:
            if prop_jobs['Idle']>0:
                glidein_max_run = int((prop_jobs['Idle'] + real) * self.fraction_running + 1)
            else:
                # no good reason for a delta when we don't need
                # more than we have
                glidein_max_run = int(real)

        return glidein_max_run

    def log_and_print_total_stats(self, total_up_stats_arr, total_down_stats_arr):
        # Log the totals
        for el in (('MatchedUp',total_up_stats_arr, True),('MatchedDown',total_down_stats_arr, False)):
            el_str,el_stats_arr,el_updown=el
            self.stats['group'].logMatchedJobs(
                el_str, el_stats_arr[0],el_stats_arr[2], el_stats_arr[3],
                el_stats_arr[5], el_stats_arr[6])

            self.stats['group'].logMatchedGlideins(el_str,el_stats_arr[8],el_stats_arr[9], el_stats_arr[10])
            self.stats['group'].logFactAttrs(el_str, [], ()) # just for completeness
            self.stats['group'].logFactDown(el_str, el_updown)
            self.stats['group'].logFactReq(el_str,el_stats_arr[11],el_stats_arr[12], {})

        # Print the totals
        # Ignore the resulting sum
        log_factory_header()
        log_and_sum_factory_line('Sum of useful factories', False, tuple(total_up_stats_arr), total_down_stats_arr)
        log_and_sum_factory_line('Sum of down factories', True, tuple(total_down_stats_arr), total_up_stats_arr)

    def log_and_print_unmatched(self, total_down_stats_arr):
        # Print unmatched... Ignore the resulting sum
        unmatched_idle = self.condorq_dict_types['Idle']['count'][(None, None, None)]
        unmatched_oldidle = self.condorq_dict_types['OldIdle']['count'][(None, None, None)]
        unmatched_running = self.condorq_dict_types['Running']['count'][(None, None, None)]

        self.stats['group'].logMatchedJobs(
            'Unmatched', unmatched_idle, unmatched_idle, unmatched_oldidle,
            unmatched_running, 0)

        self.stats['group'].logMatchedGlideins('Unmatched', 0,0,0) # Nothing running
        self.stats['group'].logFactAttrs('Unmatched', [], ()) # just for completeness
        self.stats['group'].logFactDown('Unmatched', True)
        self.stats['group'].logFactReq('Unmatched', 0, 0, {})

        this_stats_arr = (unmatched_idle, unmatched_idle, unmatched_idle, unmatched_oldidle, unmatched_idle, unmatched_running, 0, 0,
                        0, 0, 0, # glideins... none, since no matching
                        0, 0)   # requested... none, since not matching
        log_and_sum_factory_line('Unmatched', True, this_stats_arr, total_down_stats_arr)

    def choose_remove_excess_type(self, count_jobs, count_status, glideid):
        ''' Decides what kind of excess glideins to remove:
            "ALL", "IDLE", "WAIT", or "NO"
        '''
        # do not remove excessive glideins by default
        remove_excess_wait = False
        # keep track of how often idle was 0
        history_idle0 = self.history_obj.setdefault('idle0', {})
        history_idle0.setdefault(glideid, 0)

        if count_jobs['Idle'] == 0:
            # no idle jobs in the queue left
            # consider asking for unsubmitted idle glideins to be removed
            history_idle0[glideid] += 1
            if history_idle0[glideid] > 5:
                # nobody asked for anything more for some time, so
                remove_excess_wait = True
        else:
            history_idle0[glideid] = 0

        # do not remove excessive glideins by default
        remove_excess_idle = False

        # keep track of how often glideidle was 0
        history_glideempty = self.history_obj.setdefault('glideempty', {})
        history_glideempty.setdefault(glideid, 0)
        if count_status['Idle'] >= count_status['Total']:
            # no glideins being used
            # consider asking for all idle glideins to be removed
            history_glideempty[glideid] += 1
            if remove_excess_wait and (history_glideempty[glideid] > 10):
                # no requests and no glideins being used
                # no harm getting rid of everything
                remove_excess_idle = True
        else:
            history_glideempty[glideid] = 0

        # do not remove excessive glideins by default
        remove_excess_running = False

        # keep track of how often glidetotal was 0
        history_glidetotal0 = self.history_obj.setdefault('glidetotal0', {})
        history_glidetotal0.setdefault(glideid, 0)
        if count_status['Total'] == 0:
            # no glideins registered
            # consider asking for all idle glideins to be removed
            history_glidetotal0[glideid] += 1
            if remove_excess_wait and (history_glidetotal0[glideid] > 10):
                # no requests and no glidein registered
                # no harm getting rid of everything
                remove_excess_running = True
        else:
            history_glidetotal0[glideid] = 0

        if remove_excess_running:
            remove_excess_str = "ALL"
        elif remove_excess_idle:
            remove_excess_str = "IDLE"
        elif remove_excess_wait:
            remove_excess_str = "WAIT"
        else:
            remove_excess_str = "NO"
        return remove_excess_str

    def count_factory_entries_without_classads(self, total_down_stats_arr):
        # Find out the Factory entries that are running, but for which
        # Factory ClassAds don't exist
        #
        factory_entry_list=glideinFrontendLib.getFactoryEntryList(self.status_dict)
        processed_glideid_str_set=frozenset(self.processed_glideid_strs)

        factory_entry_list.sort() # sort for the sake of monitoring
        for request_name, factory_pool_node  in factory_entry_list:
            glideid_str="%s@%s"%(request_name,factory_pool_node)
            if glideid_str in processed_glideid_str_set:
                continue # already processed... ignore

            self.count_status_multi[request_name]={}
            for st in self.status_dict_types.keys():
                c = glideinFrontendLib.getClientCondorStatus(
                        self.status_dict_types[st]['dict'],
                        self.frontend_name, self.group_name,request_name)
                self.count_status_multi[request_name][st]=glideinFrontendLib.countCondorStatus(c)
                count_status=self.count_status_multi[request_name]

            # ignore matching jobs
            # since we don't have the entry classad, we have no clue how to match
            this_stats_arr=(0,0,0,0,0,0,0,0,
                            count_status['Total'],
                            count_status['Idle'],
                            count_status['Running'],
                            0,0)

            self.stats['group'].logMatchedGlideins(
                glideid_str, count_status['Total'],count_status['Idle'],
                count_status['Running'])

            # since I don't see it in the factory anymore, mark it as down
            self.stats['group'].logFactDown(glideid_str, True)
            total_down_stats_arr = log_and_sum_factory_line(
                                       glideid_str, True,
                                       this_stats_arr, total_down_stats_arr)
        return total_down_stats_arr

    def query_globals(self):
        globals_dict = {}
        try:
            # Note: M2Crypto key objects are not pickle-able,
            # so we will have to do that in the parent later on
            for factory_pool in self.factory_pools:
                factory_pool_node = factory_pool[0]
                my_identity_at_factory_pool = factory_pool[2]
                try:
                    factory_globals_dict = glideinFrontendInterface.findGlobals(factory_pool_node, None, None)
                except RuntimeError:
                    # Failed to talk or likely result is empty
                    # Maybe the next factory will have something
                    if not factory_pool_node:
                        logSupport.log.exception("Failed to talk to factory_pool %s for global info: " % factory_pool_node)
                    else:
                        logSupport.log.exception("Failed to talk to factory_pool for global info: " )
                    factory_globals_dict = {}

                for globalid in factory_globals_dict:
                    globals_el = factory_globals_dict[globalid]
                    if not globals_el['attrs'].has_key('PubKeyType'):
                        # no pub key at all, nothing to do
                        pass
                    elif globals_el['attrs']['PubKeyType'] == 'RSA':
                        # only trust RSA for now
                        try:
                            # The parent really needs just the M2Ctype object,
                            # but that is not picklable, so it will have to
                            # do it ourself
                            globals_el['attrs']['PubKeyValue'] = str(re.sub(r"\\+n", r"\n", globals_el['attrs']['PubKeyValue']))
                            globals_el['attrs']['FactoryPoolNode'] = factory_pool_node
                            globals_el['attrs']['FactoryPoolId'] = my_identity_at_factory_pool

                            # KEL: OK to put here?
                            # Do we want all globals even if there is no key?
                            # May resolve other issues with checking later on
                            globals_dict[globalid] = globals_el
                        except:
                            # if no valid key, just notify...
                            # if key needed, will handle the error later on
                            logSupport.log.warning("Factory Globals '%s': invalid RSA key" % globalid)
                            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1], sys.exc_info()[2])
                            logSupport.log.debug("Factory Globals '%s': invalid RSA key traceback: %s\n" % (globalid, str(tb)))
                    else:
                        # don't know what to do with this key, notify the admin
                        # if key needed, will handle the error later on
                        logSupport.log.info("Factory Globals '%s': unsupported pub key type '%s'" % (globalid, globals_el['attrs']['PubKeyType']))

        except Exception, ex:
            tb = traceback.format_exception(sys.exc_info()[0],
                                            sys.exc_info()[1],
                                            sys.exc_info()[2])
        return globals_dict

    def query_entries(self):
        try:
            glidein_dict = {}
            factory_constraint=expand_DD(self.elementDescript.merged_data['FactoryQueryExpr'],self.attr_dict)

            for factory_pool in self.factory_pools:
                factory_pool_node = factory_pool[0]
                factory_identity = factory_pool[1]
                my_identity_at_factory_pool = factory_pool[2]
                try:
                    factory_glidein_dict = glideinFrontendInterface.findGlideins(factory_pool_node, None, self.signatureDescript.signature_type, factory_constraint)
                except RuntimeError:
                    # Failed to talk or likely result is empty
                    # Maybe the next factory will have something
                    if factory_pool_node:
                        logSupport.log.exception("Failed to talk to factory_pool %s for entry info: " % factory_pool_node)
                    else:
                        logSupport.log.exception("Failed to talk to factory_pool for entry info: ")
                    factory_glidein_dict = {}

                for glidename in factory_glidein_dict.keys():
                    auth_id = factory_glidein_dict[glidename]['attrs'].get('AuthenticatedIdentity')
                    if not auth_id:
                        logSupport.log.warning("Found an untrusted factory %s at %s; ignoring." % (glidename, factory_pool_node))
                        break
                    if auth_id != factory_identity:
                        logSupport.log.warning("Found an untrusted factory %s at %s; identity mismatch '%s'!='%s'" % (glidename, factory_pool_node,
                                      auth_id, factory_identity))
                        break
                    glidein_dict[(factory_pool_node, glidename, my_identity_at_factory_pool)] = factory_glidein_dict[glidename]

        except Exception, ex:
            tb = traceback.format_exception(sys.exc_info()[0],
                                            sys.exc_info()[1],
                                            sys.exc_info()[2])
            logSupport.log.debug("Error in talking to the factory pool: %s" % tb)

        return glidein_dict

    def get_condor_q(self):
        try:
            condorq_format_list = self.elementDescript.merged_data['JobMatchAttrs']
            if self.x509_proxy_plugin:
                condorq_format_list = list(condorq_format_list) + list(self.x509_proxy_plugin.get_required_job_attributes())

            ### Add in elements to help in determining if jobs have voms creds
            condorq_format_list=list(condorq_format_list)+list((('x509UserProxyFirstFQAN','s'),))
            condorq_format_list=list(condorq_format_list)+list((('x509UserProxyFQAN','s'),))
            condorq_format_list=list(condorq_format_list)+list((('x509userproxy','s'),))
            condorq_dict = glideinFrontendLib.getCondorQ(
                               self.elementDescript.merged_data['JobSchedds'],
                               expand_DD(self.elementDescript.merged_data['JobQueryExpr'],self.attr_dict),
                               condorq_format_list)
        except Exception:
            logSupport.log.exception("In query schedd child, exception:")

        return condorq_dict


    def get_condor_status(self):
        status_dict={}
        fe_counts = {'Idle':0, 'Total':0}
        global_counts = {'Idle':0, 'Total':0}
        try:
            status_format_list=[]
            if self.x509_proxy_plugin:
                status_format_list=list(status_format_list)+list(self.x509_proxy_plugin.get_required_classad_attributes())

            # use the main collector... all adds must go there
            status_dict = glideinFrontendLib.getCondorStatus(
                              [None],
                              'GLIDECLIENT_Name=?="%s.%s"'%(self.frontend_name,
                                                            self.group_name),
                              status_format_list)
            # also get all the classads for the whole FE for counting
            # do it in the same thread, as we are hitting the same collector
            
            # minimize the number of attributes, since we are really just interest in the counts
            try:
                fe_status_dict=glideinFrontendLib.getCondorStatus(
                                   [None],
                                   'substr(GLIDECLIENT_Name,0,%i)=?="%s."'%(len(self.frontend_name)+1,
                                                                            self.frontend_name),
                                   [('State', 's'), ('Activity', 's')],
                                   want_format_completion=False)
                fe_counts = {
                    'Idle':glideinFrontendLib.countCondorStatus(
                        glideinFrontendLib.getIdleCondorStatus(fe_status_dict)),
                    'Total':glideinFrontendLib.countCondorStatus(fe_status_dict)}
                del fe_status_dict
            except:
                # This is not critical information, do not abort the cycle if it fails
                pass

            # same for all slots
            try:
                global_status_dict=glideinFrontendLib.getCondorStatus(
                                       [None],
                                       constraint='True', want_glideins_only=False,
                                       format_list=[('State', 's'), ('Activity', 's')],
                                       want_format_completion=False,)
                global_counts = {
                    'Idle':glideinFrontendLib.countCondorStatus(
                                        glideinFrontendLib.getIdleCondorStatus(global_status_dict)),
                    'Total':glideinFrontendLib.countCondorStatus(global_status_dict)}
                del global_status_dict
            except:
                # This is not critical information, do not abort the cycle if it fails
                pass

        except Exception, ex:
            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                            sys.exc_info()[2])
            logSupport.log.debug("Error in talking to the user pool (condor_status): %s" % tb)

        return (status_dict,fe_counts,global_counts)

    def do_match(self):
        ''' Do the actual matching.  This forks subprocess_count as children
        to do the work in parallel. '''

        logSupport.log.info("Counting subprocess created")
        pipe_ids={}
        for dt in self.condorq_dict_types.keys()+['Real','Glidein']:
            pipe_ids[dt] = fork_in_bg(self.subprocess_count, dt)

        try:
            pipe_out=fetch_fork_result_list(pipe_ids)
        except RuntimeError:
            # expect all errors logged already
            logSupport.log.exception("Terminating iteration due to errors:")
            return
        logSupport.log.info("All children terminated")

        # TODO: PM Need to check if we are counting correctly after the merge
        for dt, el in self.condorq_dict_types.iteritems():
            (el['count'], el['prop'], el['hereonly'], el['total'])=pipe_out[dt]

        self.count_real=pipe_out['Real']
        self.count_status_multi=pipe_out['Glidein']

        self.glexec='UNDEFINED'
        if 'GLIDEIN_Glexec_Use' in self.elementDescript.frontend_data:
            self.glexec=self.elementDescript.frontend_data['GLIDEIN_Glexec_Use']
        if 'GLIDEIN_Glexec_Use' in self.elementDescript.merged_data:
            self.glexec=self.elementDescript.merged_data['GLIDEIN_Glexec_Use']

    def subprocess_count(self, dt):
    # will make calculations in parallel,using multiple processes
        out = ()
        if dt=='Real':
            out = glideinFrontendLib.countRealRunning(
                      self.elementDescript.merged_data['MatchExprCompiledObj'],
                      self.condorq_dict_running, self.glidein_dict,
                      self.attr_dict, self.condorq_match_list)
        elif dt=='Glidein':
            count_status_multi={}
            for glideid in self.glidein_dict.keys():
                request_name=glideid[1]

                count_status_multi[request_name]={}
                for st in self.status_dict_types.keys():
                    c = glideinFrontendLib.getClientCondorStatus(
                            self.status_dict_types[st]['dict'],
                            self.frontend_name, self.group_name, request_name)
                    count_status_multi[request_name][st]=glideinFrontendLib.countCondorStatus(c)
            out=count_status_multi
        else:
            c,p,h = glideinFrontendLib.countMatch(
                        self.elementDescript.merged_data['MatchExprCompiledObj'],
                        self.condorq_dict_types[dt]['dict'],
                        self.glidein_dict, self.attr_dict,
                        self.condorq_match_list)
            t=glideinFrontendLib.countCondorQ(self.condorq_dict_types[dt]['dict'])
            out=(c,p,h,t)

        return out

############################################################
def check_parent(parent_pid):
    if os.path.exists('/proc/%s' % parent_pid):
        return # parent still exists, we are fine

    logSupport.log.warning("Parent died, exit.")
    raise KeyboardInterrupt, "Parent died"

############################################################
def write_stats(stats):
    for k in stats.keys():
        stats[k].write_file();

############################################################
# Will log the factory_stat_arr (tuple composed of 13 numbers)
# and return a sum of factory_stat_arr+old_factory_stat_arr
def log_and_sum_factory_line(factory, is_down, factory_stat_arr, old_factory_stat_arr):
    # if numbers are too big, reduce them to either k or M for presentation
    form_arr = []
    for i in factory_stat_arr:
        if i < 100000:
            form_arr.append("%5i" % i)
        elif i < 10000000:
            form_arr.append("%4ik" % (i / 1000))
        else:
            form_arr.append("%4iM" % (i / 1000000))

    if is_down:
        down_str = "Down"
    else:
        down_str = "Up  "

    logSupport.log.info(("%s(%s %s %s %s) %s(%s %s) | %s %s %s | %s %s " % tuple(form_arr)) + ("%s %s" % (down_str, factory)))

    new_arr = []
    for i in range(len(factory_stat_arr)):
        new_arr.append(factory_stat_arr[i] + old_factory_stat_arr[i])
    return new_arr

def init_factory_stats_arr():
    return [0] * 13

def log_factory_header():
    logSupport.log.info("            Jobs in schedd queues                 |      Glideins     |   Request   ")
    logSupport.log.info("Idle (match  eff   old  uniq )  Run ( here  max ) | Total Idle   Run  | Idle MaxRun Down Factory")

###############################
# to be used with fork clients
# Args:
#  r    - input pipe
#  pid - pid of the child
def fetch_fork_result(r,pid):
    try:
        rin=""
        s=os.read(r,1024*1024)
        while (s!=""): # "" means EOF
            rin+=s
            s=os.read(r,1024*1024) 
    finally:
        os.close(r)
        os.waitpid(pid,0)

    out=cPickle.loads(rin)
    return out

# in: pipe_is - dictionary, each element is {'r':r,'pid':pid} - see above
# out: dictionary of fork_results
def fetch_fork_result_list(pipe_ids):
    out={}
    failures=0
    for k in pipe_ids.keys():
        try:
            # now collect the results
            rin=fetch_fork_result(pipe_ids[k]['r'],pipe_ids[k]['pid'])
            out[k]=rin
        except Exception, e:
            logSupport.log.warning("Failed to retrieve %s state information from the subprocess." % k)
            logSupport.log.debug("Failed to retrieve %s state from the subprocess: %s" % (k, e))
            failures+=1
        
    if failures>0:
        raise RuntimeError, "Found %i errors"%failures

    return out
        

######################
# expand $$(attribute)
def expand_DD(qstr,attr_dict):
    robj=re.compile("\$\$\((?P<attrname>[^\)]*)\)")
    while 1:
        m=robj.search(qstr)
        if m is None:
            break # no more substitutions to do
        attr_name=m.group('attrname')
        if not attr_dict.has_key(attr_name):
            raise KeyError, "Missing attribute %s"%attr_name
        attr_val=attr_dict[attr_name]
        if type(attr_val)==type(1):
            attr_str=str(attr_val)
        else: # assume it is a string for all other purposes... quote and escape existing quotes
            attr_str='"%s"'%attr_val.replace('"','\\"')
        qstr="%s%s%s"%(qstr[:m.start()],attr_str,qstr[m.end():])
    return qstr
    

############################################################
#
# S T A R T U P
#
############################################################

if __name__ == '__main__':
    register_sighandler()
    gfe = glideinFrontendElement(int(sys.argv[1]), sys.argv[2], sys.argv[3])
    gfe.main()
