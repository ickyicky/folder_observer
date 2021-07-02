mkdir test
touch test/test.txt
touch test/test.pdf
touch test/test.zip
touch test/test.xlsx
touch test/test.py
touch test/test.docx
python observer.py -v --sort-old test
tree test
rm -rf test
