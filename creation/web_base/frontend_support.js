/*
 * Project:
 *   glideinWMS
 * 
 * File Version: 
 *   $Id: frontend_support.js,v 1.2.24.1 2010/08/31 18:49:16 parag Exp $
 *
 * Support javascript module for the frontend monitoring
 * Part of the gldieinWMS package
 *
 * Original repository: http://www.uscms.org/SoftwareComputing/Grid/WMS/glideinWMS/
 *
 */


// Load FrontendStats XML file and return the object
function loadFrontendStats() {
  var request =  new XMLHttpRequest();
  request.open("GET", "frontend_status.xml",false);
  request.send(null);
  
  var frontendStats=request.responseXML.firstChild;
  return frontendStats;
}

// Extract group names from a frontendStats XML object
function getFrontendGroups(frontendStats) {
  groups=new Array();
  for (var elc=0; elc<frontendStats.childNodes.length; elc++) {
    var el=frontendStats.childNodes[elc];
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
