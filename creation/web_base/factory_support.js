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
