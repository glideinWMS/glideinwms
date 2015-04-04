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

def get_web_url(conf_dom):
    return os.path.join(conf_dom.getElementsByTagName(u'stage')[0].getAttribute(u'web_base_url'),
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

def get_files(files_el):
    files = []
    for f in files_el.getElementsByTagName(u'file'):
        file_dict = {}
        if f.hasAttribute(u'absfname'):
            file_dict[u'absfname'] = f.getAttribute(u'absfname')
        else:
            file_dict[u'absfname'] = None
        if f.hasAttribute(u'after_entry'):
            file_dict[u'after_entry'] = f.getAttribute(u'after_entry')
        if f.hasAttribute(u'const'):
            file_dict[u'const'] = f.getAttribute(u'const')
        else:
            file_dict[u'const'] = u'False'
        if f.hasAttribute(u'executable'):
            file_dict[u'executable'] = f.getAttribute(u'executable')
        else:
            file_dict[u'executable'] = u'False'
        if f.hasAttribute(u'relfname'):
            file_dict[u'relfname'] = f.getAttribute(u'relfname')
        else:
            file_dict[u'relfname'] = None
        if f.hasAttribute(u'untar'):
            file_dict[u'untar'] = f.getAttribute(u'untar')
        else:
            file_dict[u'untar'] = u'False'
        if f.hasAttribute(u'wrapper'):
            file_dict[u'wrapper'] = f.getAttribute(u'wrapper')
        else:
            file_dict[u'wrapper'] = u'False'
        uopts = f.getElementsByTagName(u'untar_options')
        if len(uopts) > 0:
            uopt_el = f.getElementsByTagName(u'untar_options')[0]
            uopt_dict = {}
            if uopt_el.hasAttribute(u'absdir_outattr'):
                uopt_dict[u'absdir_outattr'] = uopt_el.getAttribute(u'absdir_outattr')
            else:
                uopt_dict[u'absdir_outattr'] = None
            if uopt_el.hasAttribute(u'dir'):
                uopt_dict[u'dir'] = uopt_el.getAttribute(u'dir')
            else:
                uopt_dict[u'dir'] = None
            uopt_dict[u'cond_attr'] = uopt_el.getAttribute(u'cond_attr')
            file_dict[u'untar_options'] = uopt_dict
            
        files.append(file_dict)

    return files

def get_log_retention(conf_dom):
    log_ret_dict = {}

    for log in (u'condor_logs', u'job_logs', u'summary_logs'):
        log_el = conf_dom.getElementsByTagName(log)[0]
        log_dict = {}
        log_dict[u'max_mbytes'] = log_el.getAttribute(u'max_mbytes')
        log_dict[u'min_days'] = log_el.getAttribute(u'min_days')
        log_dict[u'max_days'] = log_el.getAttribute(u'max_days')
        log_ret_dict[log] = log_dict

    log_ret_dict['process_logs'] = []
    for plog_el in conf_dom.getElementsByTagName(u'process_log'):
        plog_dict = {}
        plog_dict[u'backup_count'] = plog_el.getAttribute(u'backup_count')
        plog_dict[u'compression'] = plog_el.getAttribute(u'compression')
        plog_dict[u'extension'] = plog_el.getAttribute(u'extension')
        plog_dict[u'max_mbytes'] = plog_el.getAttribute(u'max_mbytes')
        plog_dict[u'min_days'] = plog_el.getAttribute(u'min_days')
        plog_dict[u'max_days'] = plog_el.getAttribute(u'max_days')
        plog_dict[u'msg_types'] = plog_el.getAttribute(u'msg_types')
        log_ret_dict['process_logs'].append(plog_dict)

    return log_ret_dict
         
def get_frontends(conf_dom):
    frontends = {}
    for fe_el in conf_dom.getElementsByTagName(u'frontend'):
        sec_classes = {}
        for sc_el in fe_el.getElementsByTagName(u'security_class'):
            sec_classes[sc_el.getAttribute(u'name')] = {u'username': sc_el.getAttribute(u'username')}
        frontends[fe_el.getAttribute(u'name')] = {u'security_classes': sec_classes, u'identity': fe_el.getAttribute(u'identity')}

    return frontends

def get_max_per_frontends(entry):
    per_frontends = {}
    for fe_el in entry.getElementsByTagName(u'per_frontend'):
        fe_dict = {}
        fe_dict[u'glideins'] = fe_el.getAttribute(u'glideins')
        fe_dict[u'held'] = fe_el.getAttribute(u'held')
        fe_dict[u'idle'] = fe_el.getAttribute(u'idle')
        per_frontends[fe_el.getAttribute(u'name')] = fe_dict

    return per_frontends

def get_allowed_frontends(entry):
    allowed_frontends = {}
    for fe_el in entry.getElementsByTagName(u'allow_frontend'):
        fe_dict = {}
        fe_dict[u'security_class'] = fe_el.getAttribute(u'security_class')
        allowed_frontends[fe_el.getAttribute(u'name')] = fe_dict

    return allowed_frontends

def get_submit_attrs(entry):
    submit_attrs = {}
    for attr_el in entry.getElementsByTagName(u'submit_attr'):
        attr_dict = {}
        attr_dict[u'value'] = attr_el.getAttribute(u'value')
        submit_attrs[attr_el.getAttribute(u'name')] = attr_dict

    return submit_attrs

def extract_attr_val(attr):
    if (not attr.getAttribute(u'type') in ("string","int","expr")):
        raise RuntimeError, "Wrong attribute type '%s', must be either 'int' or 'string'"%attr.getAttribute(u'type')

    if attr.getAttribute(u'type') in ("string","expr"):
        return str(attr.getAttribute(u'value'))
    else:
        return int(attr.getAttribute(u'value'))

def get_condor_attrs(attrs):
    version = None
    os = None
    arch = None 

    for attr in attrs.getElementsByTagName(u'attr'):
        if attr.getAttribute(u'name') == u'CONDOR_VERSION':
            version = attr.getAttribute(u'value')       
        elif attr.getAttribute(u'name') == u'CONDOR_OS':
            os = attr.getAttribute(u'value')       
        elif attr.getAttribute(u'name') == u'CONDOR_ARCH':
            arch = attr.getAttribute(u'value')       

        if version is not None and os is not None and arch is not None:
            break
    
    return (version,os,arch)
