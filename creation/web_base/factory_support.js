/*
 * Project:
 *   glideinWMS
 *
 * File Version: 
 *   $Id: factory_support.js,v 1.3.8.4.8.1 2010/08/31 18:49:16 parag Exp $
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
