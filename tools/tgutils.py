class FrontendConfig:
    def __init__(self):
        self.factory_id = "glidefactory"
        self.factory_global = "glidefactoryglobal"
        self.client_id = "glideclient"
        self.client_global = "glideclientglobal"
        self.factoryclient_id = "glidefactoryclient"
        self.glidein_attr_prefix = ""
        self.glidein_param_prefix = "GlideinParam"
        self.encrypted_param_prefix = "GlideinEncParam"
        self.glidein_monitor_prefix = "GlideinMonitor"
        self.glidein_config_prefix = "GlideinConfig"
        self.glidein_perfmetric_prefix = "GlideinPerfMetric"
        self.client_req_prefix = "Req"
        self.factory_signtype_id = "SupportedSignTypes"
        self.advertise_use_tcp = False
        self.advertise_use_multi = False
        self.condor_reserved_names = ("MyType", "TargetType", "GlideinMyType", "MyAddress", 'UpdatesHistory', 'UpdatesTotal', 'UpdatesLost', 'UpdatesSequenced', 'UpdateSequenceNumber', 'DaemonStartTime')

frontendConfig = FrontendConfig()
def format_condor_dict(data):
    reserved_names = frontendConfig.condor_reserved_names
    for k in reserved_names:
        if data.has_key(k):
            del data[k]

    out = {}

    for k in data.keys():
        kel = data[k].copy()

        el = {"params":{}, "monitor":{}}

        # first remove reserved anmes
        for attr in reserved_names:
            if kel.has_key(attr):
                del kel[attr]

        # then move the parameters and monitoring
        for (prefix, eldata) in ((frontendConfig.glidein_param_prefix, el["params"]),
                              (frontendConfig.glidein_monitor_prefix, el["monitor"])):
            plen = len(prefix)
            for attr in kel.keys():
                if attr[:plen] == prefix:
                    eldata[attr[plen:]] = kel[attr]
                    del kel[attr]

        # what is left are glidein attributes
        el["attrs"] = kel

        out[k] = el

    return out

