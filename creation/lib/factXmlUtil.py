import os

def get_submit_dir(conf_dom):
    return os.path.join(conf_dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_dir'),
        u"glidein_%s" % conf_dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))

def get_stage_dir(conf_dom):
    return os.path.join(conf_dom.getElementsByTagName(u'stage')[0].getAttribute(u'base_dir'),
        u"glidein_%s" % conf_dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))

def get_monitor_dir(conf_dom):
    return os.path.join(conf_dom.getElementsByTagName(u'monitor')[0].getAttribute(u'base_dir'),
        u"glidein_%s" % conf_dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))

def get_log_dir(conf_dom):
    return os.path.join(conf_dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_log_dir'),
        u"glidein_%s" % conf_dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name'))

def get_client_log_dirs(conf_dom):
    cl_dict = {}
    client_dir = conf_dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_client_log_dir')
    glidein_name = conf_dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name')
    for sc in conf_dom.getElementsByTagName(u'security_class'):
        cl_dict[sc.getAttribute(u'username')] = os.path.join(client_dir,
            u"user_%s" % sc.getAttribute(u'username'), u"glidein_%s" % glidein_name)

    return cl_dict

def get_client_proxy_dirs(conf_dom):
    cp_dict = {}
    client_dir = conf_dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_client_proxies_dir')
    glidein_name = conf_dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name')
    for sc in conf_dom.getElementsByTagName(u'security_class'):
        cp_dict[sc.getAttribute(u'username')] = os.path.join(client_dir,
            u"user_%s" % sc.getAttribute(u'username'), u"glidein_%s" % glidein_name)

    return cp_dict

def get_condor_tarballs(conf_dom):
    tarballs = []
    for tb in conf_dom.getElementsByTagName(u'condor_tarball'):
        tb_dict = {}
        tb_dict[u'arch'] = tb.getAttribute(u'arch')
        tb_dict[u'os'] = tb.getAttribute(u'os')
        tb_dict[u'tar_file'] = tb.getAttribute(u'tar_file')
        tb_dict[u'version'] = tb.getAttribute(u'version')
        tarballs.append(tb_dict)

    return tarballs
