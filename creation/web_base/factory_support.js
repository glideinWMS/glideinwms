/*
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

// Extract group names from each entry XML object
function getFactoryEntryGroups(factoryQStats) {
  groups=new Array();
  for (var elc=0; elc<factoryQStats.childNodes.length; elc++) {
    var el=factoryQStats.childNodes[elc];
    if ((el.nodeType==1) && (el.nodeName=="entries")) {
      for (var etc=0; etc<el.childNodes.length; etc++) {
	var entry=el.childNodes[etc];
	if ((entry.nodeType==1)&&(entry.nodeName=="entry")) {
	  var entry_name=entry.attributes.getNamedItem("name");
          for (var etgs=0; etgs<entry.childNodes.length; etgs++) {
            var grps=entry.childNodes[etgs];
	    if ((grps.nodeType==1)&&(grps.nodeName=="monitor")) {
              for (var etg=0; etg<grps.childNodes.length; etg++) {
                var grp=grps.childNodes[etg];
	        if ((grp.nodeType==1)&&(grp.nodeName=="group")) {
	          var group_name=grp.attributes.getNamedItem("name");
                  if (group_name.value in groups) {
                    (groups[group_name.value]).push(entry_name.value);
                  } 
                  else {
                    groups[group_name.value] = new Array();
                    (groups[group_name.value]).push(entry_name.value);
                  }
	          //groups.push(group_name.value);
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
