/*
 * Project:
 *   glideinWMS
 *
 * File Version: 
 *
 * Support javascript module for the gfactroy monitoring
 * Part of the gldieinWMS package
 *
 * Original repository: http://www.uscms.org/SoftwareComputing/Grid/WMS/glideinWMS/
 *
 */

// Load FactoryQStats XML file and return the object
function loadFactoryQStats() {
  var request =  new XMLHttpRequest();
  request.open("GET", "schedd_status.xml",false);
  request.send(null);
  
  var factoryQStats=request.responseXML.firstChild;
  return factoryQStats;
}

// Extract entry names from a factoryQStats XML object
function getFactoryEntries(factoryQStats) {
  entries=new Array();
  for (var elc=0; elc<factoryQStats.childNodes.length; elc++) {
    var el=factoryQStats.childNodes[elc];
    if ((el.nodeType==1) && (el.nodeName=="entries")) {
      for (var etc=0; etc<el.childNodes.length; etc++) {
	var entry=el.childNodes[etc];
	if ((entry.nodeType==1)&&(entry.nodeName=="entry")) {
	  var entry_name=entry.attributes.getNamedItem("name");
	  entries.push(entry_name.value);
	}
      }
    }
  }
  return entries;
}

// Get monitor_config. If not present return factoryQStats
function loadMonitorConfig() {
  try {
    var request =  new XMLHttpRequest();
    request.open("GET", "monitor.xml",false)
    request.send(null);
    var factoryQStats=request.responseXML.firstChild;
    return factoryQStats;
    //return request.responseXML.firstChild;
  } catch (err) {
    return loadFactoryQStats;
  }
}

function getFactoryFrontends(factoryQStats){
  var factoryQStats = loadFactoryQStats();
  groups=new Array();
  for (var elc=0; elc<factoryQStats.childNodes.length; elc++) {
    var el=factoryQStats.childNodes[elc];
    if (el.nodeName=="frontends"){
        groups["total"]=new Array();
        for (var sei=0; sei<el.childNodes.length; sei++){
            var thisval=el.childNodes[sei];
            if (thisval.nodeName=="frontend"){
                var front_name=thisval.attributes[0].value.toString();
                groups["total"].push(front_name);
            }
        }
    }
    if (el.nodeName=="entries") {
      for (var etc=0; etc<el.childNodes.length; etc++) {
	var entry=el.childNodes[etc];
	if (entry.nodeName=="entry") {
	  var entry_name=entry.attributes.getNamedItem("name");
          groups[entry_name.value]=new Array();
          for (var a=0; a<entry.childNodes.length;a++) {
	     var el2=entry.childNodes[a];
             if(el2.nodeName=="frontends") {
               for (var b=0; b<el2.childNodes.length;b++) {
                 var el3=el2.childNodes[b];
                 if(el3.nodeName=="frontend") { 
                   var frontend_name=el3.attributes[0].value.toString();
                   groups[entry_name.value].push(frontend_name);
  }}}}}}}}
  return groups;
}

// Extract group names from each entry XML object
function getFactoryEntryGroups(factoryQStats) {
  var factoryQStats = loadMonitorConfig();
  groups=new Array();
  for (var elc=0; elc<factoryQStats.childNodes.length; elc++) {
    var el=factoryQStats.childNodes[elc];
    if ((el.nodeType==1) && (el.nodeName=="entries")) {
      for (var etc=0; etc<el.childNodes.length; etc++) {
	var entry=el.childNodes[etc];
	if ((entry.nodeType==1)&&(entry.nodeName=="entry")) {
	  var entry_name=entry.attributes.getNamedItem("name");
          if (entry_name.value in groups) {
            (groups[entry_name.value]).push(entry_name.value);
          } 
          else {
            groups[entry_name.value] = new Array();
            (groups[entry_name.value]).push(entry_name.value);
          }
          for (var etgs=0; etgs<entry.childNodes.length; etgs++) {
            var grps=entry.childNodes[etgs];
	    if ((grps.nodeType==1)&&(grps.nodeName=="monitorgroups")) {
              for (var etg=0; etg<grps.childNodes.length; etg++) {
                var grp=grps.childNodes[etg];
	        if ((grp.nodeType==1)&&(grp.nodeName=="monitorgroup")) {
	          var group_name=grp.attributes.getNamedItem("group_name");
                  if (group_name.value in groups) {
                    (groups[group_name.value]).push(entry_name.value);
                  } 
                  else {
                    groups[group_name.value] = new Array();
                    (groups[group_name.value]).push(entry_name.value);
                  }
                }
              }
            }
	  }
	}
      }
    }
  }
  return groups;
}


/* LOAD DESCRIPT FOR FACTORY AND GLIDEIN NAME */
function set_title_and_footer(browser_title, page_title)
{
	var xmlhttp_descript;
	var factory_name;
	var glidein_name;
	
	if(window.XMLHttpRequest)
	{
		xmlhttp_descript=new XMLHttpRequest();
	}
	else
	{
		xmlhttp_descript=new ActiveXObject("Microsoft.XMLHTTP");
	}
	  
	xmlhttp_descript.onreadystatechange=function()
	{	
		if (xmlhttp_descript.readyState == 4) //4 == READY
    	{
    	    factory_info = xmlhttp_descript.responseXML.documentElement.getElementsByTagName("factory");
    	    
			for (var i=0; i<factory_info[0].attributes.length; i++) {
				if (factory_info[0].attributes[i].name == "FactoryName") {
					factory_name = factory_info[0].attributes[i].value;
				}
				if (factory_info[0].attributes[i].name == "GlideinName") {
					glidein_name = factory_info[0].attributes[i].value;
				}
				
				if (factory_info[0].attributes[i].name == "MonitorDisplayText") {
					footer_text = factory_info[0].attributes[i].value;
				}
				if (factory_info[0].attributes[i].name == "MonitorLink") {
					footer_link = factory_info[0].attributes[i].value;
				}
        	}   
			document.getElementById("pgtitle").innerHTML= page_title + " - " + glidein_name + "@" + factory_name; 
			document.getElementById("brtitle").innerHTML= browser_title + " - " + glidein_name + "@" + factory_name;
        	
        	if (footer_text != "") {
        		var a_tag = document.createElement('a');
        		a_tag.appendChild(document.createTextNode(footer_text));
        		a_tag.setAttribute("href", footer_link);
        		document.getElementById("monitor_footer").appendChild(a_tag); 
        	}  
		} 	 
	}
	xmlhttp_descript.open("GET", "descript.xml",true);
	xmlhttp_descript.send(null);
}
