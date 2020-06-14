import subprocess
import pdfcutter

def showCutter(page,  pageNumber=None):
    cutter = page.cutter
    debugger = page.cutter.get_debugger()
    if pageNumber == None: #Get first page with some part of selection
        pageNumber = min(page.pages, key= lambda x: x.number).number
    d1 = debugger.debug(page, page=pageNumber) #INFO Really need this pagenumber here, else DEBUG: FC_WEIGHT didn't match error here
    #page = cutter.filter(page=pageNumber)
    d = d1.get_page_as_html(pageNumber) # gibt dir bild zurück
    #TODO Tmp absolute file
#    outfile = "TMPselected.html"
    outfile = subprocess.check_output("mktemp")[:-1].decode("ascii") #Remove \n at the end + bytes to str (Needed for e.g. mktemp)
    with open(outfile, "w") as file:
        file.write(d)
    subprocess.Popen(["firefox",outfile] )

