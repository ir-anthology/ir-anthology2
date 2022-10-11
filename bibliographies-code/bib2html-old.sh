#!/usr/bin/env bash

set -e

code=$(dirname $0)
publications=$code/../bibliographies-webis

echo ""
echo "... generating bib-pan.html"
php ${code}/bib2html.php pan ${publications}/pan-publications.bib > ${code}/bib-pan.html

echo ""
echo "Todo: Please upload the bib-pan.html file (if you changed pub-pan.bib) here: https://github.com/pan-webis-de/pan-webis-de.github.io/tree/master/_includes"

echo ""
echo "... generating bib-touche.html"
php ${code}/bib2html.php touche ${publications}/touche-publications.bib > ${code}/bib-touche.html

echo ""
echo "Todo: Please upload the bib-touche.html file (if you changed pub-touche.bib) here: https://github.com/touche-webis-de/touche-webis-de.github.io/tree/master/_includes"

echo ""
echo "... generating bib-webis.html"
php ${code}/bib2html.php webis ${publications}/webis-publications.bib > ${code}/bib-webis.html

echo ""
echo "... generating bib-theses.html"
php ${code}/bib2html.php theses ${publications}/webis-theses.bib > ${code}/bib-theses.html

echo ""
echo "Todo: Please upload the bib-webis.html and bib-theses.html  (if you changed webis-publications.bib or webis-theses.bib) here: https://github.com/webis-de/webis-de.github.io/tree/master/_includes"

echo ""
echo ""
