/*
 * Project:
 *   glideinWMS
 * 
 * File Version: 
 *   $Id: frontend_support.js,v 1.2.8.3 2011/07/05 19:25:55 sfiligoi Exp $
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

//Extract factory or state names from frontendStats XML obj
function getFrontendGroupFoS(frontendStats, group_name, fos_tag_top, fos_tag_one) {
  factories=new Array();

  if(group_name=="total") {
    for (var i=0; i<frontendStats.childNodes.length; i++) {
      var el=frontendStats.childNodes[i];
      if ((el.nodeType==1) && (el.nodeName==fos_tag_top)) {
        for (var j=0; j<el.childNodes.length; j++) {
  	  var group=el.childNodes[j];
            if ((group.nodeType==1)&&(group.nodeName==fos_tag_one)) {
              var group_name=group.attributes.getNamedItem("name");
	      factories.push(group_name.value);
	    }
          }
       }
    } 
    return factories;
  }

  for (var i=0; i<frontendStats.childNodes.length; i++) {
    var el=frontendStats.childNodes[i];
    if ((el.nodeType==1) && (el.nodeName=="groups")) {
      for (var j=0; j<el.childNodes.length; j++) {
	var group=el.childNodes[j];
	if ((group.nodeType==1)&&(group.nodeName=="group")) {
	  var group_name1=group.attributes.getNamedItem("name").value;
          if(group_name1==group_name) {
             for(var k=0; k<group.childNodes.length; k++) { 
               var el2 = group.childNodes[k];
               if (el2.nodeName==fos_tag_top) {
                  for(var m=0; m<el2.childNodes.length; m++) { 
                     var factory = el2.childNodes[m];
                     if(factory.nodeName==fos_tag_one) {
                        factory_name=factory.attributes.getNamedItem("name");
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
 var out="";
 for (var i=0; i<name.length; i++) {
  var c=name.charAt(i);
  if (c.search('[A-z0-9\-.]')==-1) {
    out=out.concat('_');
  } else {
    out=out.concat(c);
  }
 }
 return out; 
}

function getRRDName(rrd_fname,group_name,factory_name,frontendStats) {
  if (factory_name=="total") {
    if (group_name=="total") {
      fname="total/"+rrd_fname+".rrd";
    } else {
      fname="group_"+group_name+"/total/"+rrd_fname+".rrd";
    }
  } else {
    var states = getFrontendGroupStates(frontendStats, group_name);

    fos_prefix="factory_";
    // seach through the array
    // quick hack, could be optimized
    for(var state in states) {
      state_name = states[state];
      if (state_name==factory_name) {
	// it is a state, not a factory
	fos_prefix="state_";
	break;
      }
    }

    if(group_name=="total") {
      fname="total/"+fos_prefix+sanitize(factory_name)+"/"+rrd_fname+".rrd";
    } else {
      fname="group_"+group_name+"/"+fos_prefix+sanitize(factory_name)+"/"+rrd_fname+".rrd";
    }
  }
  return fname;
}
