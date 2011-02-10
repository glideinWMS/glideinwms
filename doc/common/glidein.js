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
    var customSearchControl = new google.search.CustomSearchControl('006450287401290132076:v1ncvuycvmi');
    customSearchControl.setResultSetSize(google.search.Search.FILTERED_CSE_RESULTSET);
    var options = new google.search.DrawOptions();
    options.setSearchFormRoot('cse-search-form');
    customSearchControl.draw('cse', options);
    customSearchControl.setSearchCompleteCallback(null, searchComplete);
}
