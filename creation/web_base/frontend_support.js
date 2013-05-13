/*
* Project:
*   glideinWMS
*
* File Version:
*
* Support javascript module for the frontend monitoring
* Part of the gldieinWMS package
*
* Original repository: http://www.uscms.org/SoftwareComputing/Grid/WMS/glideinWMS/
*
*/

// Load FrontendStats XML file and return the object
function loadFrontendStats() {
    var request = new XMLHttpRequest();
    request.open("GET", "frontend_status.xml", false);
    request.send(null);

    var frontendStats = request.responseXML.firstChild;
    return frontendStats;
}


// Extract group names from a frontendStats XML object
function getFrontendGroups(frontendStats) {
    groups = new Array();
    for (var elc = 0; elc < frontendStats.childNodes.length; elc++) {
        var el = frontendStats.childNodes[elc];
        if ((el.nodeType == 1) && (el.nodeName == "groups")) {
            for (var etc = 0; etc < el.childNodes.length; etc++) {
                var group = el.childNodes[etc];
                if ((group.nodeType == 1) && (group.nodeName == "group")) {
                    var group_name = group.attributes.getNamedItem("name");
                    groups.push(group_name.value);
                }
            }
        }
    }
    return groups;
}


//Extract factory or state names from frontendStats XML obj
function getFrontendGroupFoS(frontendStats, group_name, fos_tag_top, fos_tag_one) {
    factories = new Array();

    if (group_name == "total") {
        for (var i = 0; i < frontendStats.childNodes.length; i++) {
            var el = frontendStats.childNodes[i];
            if ((el.nodeType == 1) && (el.nodeName == fos_tag_top)) {
                for (var j = 0; j < el.childNodes.length; j++) {
                    var group = el.childNodes[j];
                    if ((group.nodeType == 1) && (group.nodeName == fos_tag_one)) {
                        var group_name = group.attributes.getNamedItem("name");
                        factories.push(group_name.value);
                    }
                }
            }
        }
        return factories;
    }

    for (var i = 0; i < frontendStats.childNodes.length; i++) {
        var el = frontendStats.childNodes[i];
        if ((el.nodeType == 1) && (el.nodeName == "groups")) {
            for (var j = 0; j < el.childNodes.length; j++) {
                var group = el.childNodes[j];
                if ((group.nodeType == 1) && (group.nodeName == "group")) {
                    var group_name1 = group.attributes.getNamedItem("name").value;
                    if (group_name1 == group_name) {
                        for (var k = 0; k < group.childNodes.length; k++) {
                            var el2 = group.childNodes[k];
                            if (el2.nodeName == fos_tag_top) {
                                for (var m = 0; m < el2.childNodes.length; m++) {
                                    var factory = el2.childNodes[m];
                                    if (factory.nodeName == fos_tag_one) {
                                        factory_name = factory.attributes.getNamedItem("name");
                                        factories.push(factory_name.value);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    return factories;
}


//Extract factory names from frontendStats XML obj
function getFrontendGroupFactories(frontendStats, group_name) {
    return getFrontendGroupFoS(frontendStats, group_name, "factories", "factory")
}


//Extract state names from frontendStats XML obj
function getFrontendGroupStates(frontendStats, group_name) {
    return getFrontendGroupFoS(frontendStats, group_name, "states", "state")
}


function sanitize(name) {
    var out = "";
    for (var i = 0; i < name.length; i++) {
        var c = name.charAt(i);
        if (c.search('[A-z0-9\-.]') == -1) {
            out = out.concat('_');
        }
        else {
            out = out.concat(c);
        }
    }
    return out;
}


function generate_navbar() {
    var frontendname = get_frontend_name();

    var menu_items = [['Home', 'index.html', 'Frontend Monitoring Home'], ['Browse', 'frontendRRDBrowse.html', 'Browse Frontend RRDs'], ['Group Matrix', 'frontendRRDGroupMatrix.html', 'RRD Matrix by Frontend Groups'], ['Status', 'frontendStatus.html', 'Frontend Status'], ['Current Status', 'frontendGroupGraphStatusNow.html', 'Current Frontend Status']]

    // Get a handle to the navbar div
    var navbar_inner = document.getElementById('navbar-inner');

    // Add the navbar title
    var navbar_title = document.createElement('a');
    navbar_title.setAttribute('class', 'brand');
    navbar_title.setAttribute('href', 'http://www.uscms.org/SoftwareComputing/Grid/WMS/glideinWMS');
    navbar_title.innerHTML = 'GlideinWMS Frontend';
    navbar_inner.appendChild(navbar_title);

    // Generate the navbar menu
    var navbar_menu = document.createElement('ul');
    navbar_menu.setAttribute('class', 'nav');
    navbar_menu.setAttribute('id', 'navbar-menu');
    navbar_inner.appendChild(navbar_menu);

    for (var i = 0; i < menu_items.length; i++) {
        var li_class = "";
        l = location.pathname.substring(location.pathname.lastIndexOf("/") + 1);
        if (l == menu_items[i][1]) {
            li_class = " class='active' ";
        }
        var li = "<li" + li_class + "><a title='" + menu_items[i][2] + "' href='" + menu_items[i][1] + "'>" + menu_items[i][0] + "</a></li>";
        $("#navbar-menu").append(li);
    }
}


function get_frontend_name() {
    var xmlhttp_descript;
    var frontend_name = "";

    if (window.XMLHttpRequest) {
        xmlhttp_descript = new XMLHttpRequest();
    }
    else {
        xmlhttp_descript = new ActiveXObject("Microsoft.XMLHTTP");
    }

    xmlhttp_descript.open("GET", "descript.xml", false);
    xmlhttp_descript.send(null);

    frontend_info = xmlhttp_descript.responseXML.documentElement.getElementsByTagName("frontend");
    frontend_name = frontend_info[0].attributes[0].value;
    return frontend_name;
}


function draw_powered_footer(div_id) {
    var powered_by = [['RRDTool', 'http://oss.oetiker.ch/rrdtool'], ['JavascriptRRD', 'https://sourceforge.net/projects/javascriptrrd'], ['Flot', 'http://www.flotcharts.org']];

    var footer_div = document.getElementById(div_id);
    footer_div.setAttribute('class', 'powered-footer');
    var p = document.createElement('p');
    footer_div.innerHTML = "Powered By:  ";
    for (var i = 0; i < powered_by.length; i++) {
        var link = "<a href='" + powered_by[i][1] + "' target='_blank'>" + powered_by[i][0] + "</a>&nbsp;&nbsp;"
        footer_div.innerHTML += link;
    }
}


/* LOAD DESCRIPT FOR FRONTEND NAME */
function set_title_and_footer(browser_title, page_title) {
    var xmlhttp_descript;
    var frontend_name;

    if (window.XMLHttpRequest) {
        xmlhttp_descript = new XMLHttpRequest();
    }
    else {
        xmlhttp_descript = new ActiveXObject("Microsoft.XMLHTTP");
    }

    xmlhttp_descript.onreadystatechange = function() {
        //4 == READY
        if (xmlhttp_descript.readyState == 4) {
            frontend_info = xmlhttp_descript.responseXML.documentElement.getElementsByTagName("frontend");
            frontend_name = frontend_info[0].attributes[0].value;
            if (document.getElementById("pgtitle")) {
                document.getElementById("pgtitle").innerHTML = page_title + " - " + frontend_name;
            }
            document.getElementById("brtitle").innerHTML = browser_title + " - " + frontend_name;
            footer_info = xmlhttp_descript.responseXML.documentElement.getElementsByTagName("monitor_footer");
            footer_text = footer_info[0].attributes[0].value;
            footer_link = footer_info[0].attributes[1].value;
            if (footer_text.trim() != '') {
                var a_tag = document.createElement('a');
                a_tag.appendChild(document.createTextNode(footer_text.trim()));
                a_tag.setAttribute("href", footer_link);
                var mon_footer = document.getElementById("monitor_footer");
                mon_footer.setAttribute('class', 'monitor-footer');
                mon_footer.appendChild(a_tag);
            }
        }
    }
    xmlhttp_descript.open("GET", "descript.xml", true);
    xmlhttp_descript.send(null);
}


function getRRDName(rrd_fname, group_name, factory_name, frontendStats) {
    if (factory_name == "total") {
        if (group_name == "total") {
            fname = "total/" + rrd_fname + ".rrd";
        }
        else {
            fname = "group_" + group_name + "/total/" + rrd_fname + ".rrd";
        }
    }
    else {
        var states = getFrontendGroupStates(frontendStats, group_name);

        fos_prefix = "factory_";
        // seach through the array
        // quick hack, could be optimized
        for (var state in states) {
            state_name = states[state];
            if (state_name == factory_name) {
                // it is a state, not a factory
                fos_prefix = "state_";
                break;
            }
        }

        if (group_name == "total") {
            fname = "total/" + fos_prefix + sanitize(factory_name) + "/" + rrd_fname + ".rrd";
        }
        else {
            fname = "group_" + group_name + "/" + fos_prefix + sanitize(factory_name) + "/" + rrd_fname + ".rrd";
        }
    }

    return fname;
}


String.prototype.trim = function() {
    return this.replace(/^\s+|\s+$/g, '');
};
