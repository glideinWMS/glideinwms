function findByClass(tagName, className) {
    var r = new RegExp('\\b' + className + '\\b');
    var elements = document.getElementsByTagName(tagName);
    for (var i = 0;  i < elements.length;  i++) {
      var e = elements[i];
      if (e.className && r.test(e.className)) {
        return e;
      }
    }
    return null;
  }


  function searchComplete() {
    document.getElementById('searchcontent')
      .style.display = 'block';
    var e=findByClass("div","content");
    e.style.display = 'none';
  }


function onLoad() {
    // old www.uscms.org/SoftwareComputing/Grid/WMS/glideinWMS/ (cse - ?) 006450287401290132076:v1ncvuycvmi
    // glideinwms.fnal.gov/doc.prd (cse - Marco Mambelli) : 013439253731257915088:h-xvmglqvrq 
    var customSearchControl = new google.search.CustomSearchControl('013439253731257915088:h-xvmglqvrq');
    customSearchControl.setResultSetSize(google.search.Search.FILTERED_CSE_RESULTSET);
    var options = new google.search.DrawOptions();
    options.setSearchFormRoot('cse-search-form');
    customSearchControl.draw('cse', options);
    customSearchControl.setSearchCompleteCallback(null, searchComplete);
}
