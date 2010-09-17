make html
#scp -r build catherine@$tummy:/var/www/sqlpython
cd _build/html
zip -r cmd2_docs *
mv cmd2_docs.zip ../..
cd ..
echo "Upload cmd2_docs.zip to http://pypi.python.org/pypi?%3Aaction=pkg_edit&name=cmd2"
scp -r _build/html www-data@$tummy:/var/www/cmd2
