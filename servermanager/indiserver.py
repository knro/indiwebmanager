import PyIndiServer
import parsedrivers
import sys

def startServer(port, drivers):
    #PyIndiServer.logStartup(argv)
    #verbosity
    PyIndiServer.cvar.verbose=1
    PyIndiServer.noZombies()
    PyIndiServer.noSIGPIPE()
    # Drivers
    # step 1: build an initial list of empty drivers in python and set their names
    dvrinfo=[] # we won't keep this copy as it won't be up to date
    for driver in drivers:
        dvr=PyIndiServer.DvrInfo()
        dvr.name=driver.binary
        dvrinfo.append(dvr)

    # step 2: assign the global C variable dvrinfo to this list:
    # performs the malloc (no free yet) and also sets the global C variable ndvrinfo
    PyIndiServer.cvar.dvrinfo=dvrinfo

    # step 3: start the drivers (those in the global C variable)
    for d in PyIndiServer.cvar.dvrinfo:
        PyIndiServer.startDvr(d)

    # as for now, always use the global variable to access/refresh the driver info
    #pdvr=PyIndiServer.cvar.dvrinfo
    #for d in pdvr:
    #    print d.name, d.active, d.ndev, d.pid, d.rfd, d.efd, d.wfd, d.nsent 
    #Clients
    # just allocate the initial array
    PyIndiServer.port = port
    PyIndiServer.cvar.nclinfo=0
    PyIndiServer.cvar.clinfo=PyIndiServer.calloc_ClInfo(PyIndiServer.cvar.nclinfo)

    # always use the global variable to access/refresh the client info
    pcl=PyIndiServer.cvar.clinfo

    PyIndiServer.indiListen()

    PyIndiServer.cvar.fifo.name='/tmp/indiFIFO'
    PyIndiServer.indiFIFO()
    PyIndiServer.indiRun()
    
def stopServer():
    PyIndiServer.Bye()
