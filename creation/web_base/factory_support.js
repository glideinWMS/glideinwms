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
                var front_name=thisval.attributes[0].nodeValue.toString();
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
                   var frontend_name=el3.attributes[0].nodeValue.toString();
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
