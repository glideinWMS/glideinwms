/*
 * Support javascript module for the frontend monitoring
 * Part of the gldieinWMS package
 *
 * Original repository: http://www.uscms.org/SoftwareComputing/Grid/WMS/glideinWMS/
 *
 */

// To be finished... mostly a placeholder for now

// Load FrontendQStats XML file and return the object
function loadFrontendQStats() {
  var request =  new XMLHttpRequest();
  request.open("GET", "schedd_status.xml",false);
  request.send(null);
  
  var frontendQStats=request.responseXML.firstChild;
  return frontendQStats;
}

// Extract group names from a frontendQStats XML object
function getFrontendGroups(frontendQStats) {
  groups=new Array();
  for (var elc=0; elc<frontendQStats.childNodes.length; elc++) {
    var el=frontendQStats.childNodes[elc];
    if ((el.nodeType==1) && (el.nodeName=="groups")) {
      for (var etc=0; etc<el.childNodes.length; etc++) {
	var group=el.childNodes[etc];
	if ((group.nodeType==1)&&(group.nodeName=="group")) {
	  var group_name=group.attributes.getNamedItem("name");
	  groups.push(group_name.value);
	}
      }
    }
  }
  return groups;
}
