<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">

<!-- If IE use the latest rendering engine -->
<meta http-equiv="X-UA-Compatible" content="IE=edge">

<!-- Set the page to the width of the device and set the zoon level -->
<meta name="viewport" content="width = device-width, initial-scale = 1">
<title>Bootstrap Tutorial</title>
<link rel="stylesheet" type="text/css" href="/static/css/bootstrap.css">

<style>
.jumbotron{
    background-color:#2E2D88;
    color:white;
}
/* Adds borders for tabs */
.tab-content {
    border-left: 1px solid #ddd;
    border-right: 1px solid #ddd;
    border-bottom: 1px solid #ddd;
    padding: 10px;
}
.nav-tabs {
    margin-bottom: 0;
}
</style>

</head>
<body>

%if (runningDrivers):
    %mount = next((x for x in runningDrivers if x.family=="Telescopes"), False)


<div class="container">
    
    <div class="page-header"><h1>INDI Server Manager</h1></div>                            

<div class="row">    

  <form class="form-horizontal">  
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label for="Mount">Mount</label>
%if (mount):
    <select name="mount_driver" class="form-control" disabled>
%else:
    <select name="mount_driver" class="form-control">
%end
    <option>--</option>
%for driver in driversList:
%if (driver.family == "Telescopes"):
    %if (mount and mount.name == driver.name):
        <option selected>{{driver.label}}</option>
    %else:
        <option>{{driver.label}}</option>
    %end
%end
%end
    </select>
  </div>
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label for="CCD">CCD</label>
    <select name="ccd_driver" class="form-control">
    <option>--</option>
%for driver in driversList:
%if (driver.family == "CCDs"):
        <option>{{driver.label}}</option>
%end
%end
    </select>
  </div>
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label for="Guider">Guider</label>
    <select name="guider_driver" class="form-control">
        <option>--</option>
%for driver in driversList:
%if (driver.family == "CCDs"):
        <option>{{driver.label}}</option>
%end
%end
    </select>
  </div>
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label for="Focuser">Focuser</label>
    <select name="focuser_driver" class="form-control">
        <option>--</option>
%for driver in driversList:
%if (driver.family == "Focusers"):
        <option>{{driver.label}}</option>
%end
%end
    </select>
  </div>
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label for="Filter">Filter</label>
    <select name="filter_driver" class="form-control">
        <option>--</option>
%for driver in driversList:
%if (driver.family == "Filter Wheels"):
        <option>{{driver.label}}</option>
%end
%end
    </select>
  </div>
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label for="Adaptive Optics">AO</label>
    <select name="ao_driver" class="form-control">
        <option>--</option>
%for driver in driversList:
%if (driver.family == "Adaptive Optics"):
        <option>{{driver.label}}</option>
%end
%end        
    </select>
  </div>
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label for="Dome">Dome</label>
    <select name="dome_driver" class="form-control">
        <option>--</option>
%for driver in driversList:
%if (driver.family == "Domes"):
        <option>{{driver.label}}</option>
%end
%end        
    </select>
  </div>
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label for="Weather">Weather</label>
    <select name="weather_driver" class="form-control">
        <option>--</option>
%for driver in driversList:
%if (driver.family == "Weather"):
        <option>{{driver.label}}</option>
%end
%end
    </select>
  </div>
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label for="Auxiliary 1">Aux1</label>
    <select name="aux1_driver" class="form-control">
        <option>--</option>
%for driver in driversList:
%if (driver.family == "CCDs" or driver.family == "Auxiliary"):
        <option>{{driver.label}}</option>
%end
%end
    </select>
  </div>
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label for="Auxiliary 2">Aux2</label>
    <select name="aux2_driver" class="form-control">
        <option>--</option>
%for driver in driversList:
%if (driver.family == "CCDs" or driver.family == "Auxiliary"):
        <option>{{driver.label}}</option>
%end
%end
    </select>
  </div>
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label for="Auxiliary 3">Aux3</label>
    <select name="aux3_driver" name="aux3" class="form-control">
        <option>--</option>
%for driver in driversList:
%if (driver.family == "CCDs" or driver.family == "Auxiliary"):
        <option>{{driver.label}}</option>
%end
%end
    </select>
  </div>  
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label for="Auxiliary 4">Aux4</label>
    <select name="aux4_driver" class="form-control">
        <option>--</option>
%for driver in driversList:
%if (driver.family == "CCDs" or driver.family == "Auxiliary"):
        <option>{{driver.label}}</option>
%end
%end
    </select>
  </div>
  
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
  <button class="btn btn-default" name="indiaction" type="submit" value="start_server">Start</button>
  </div>
  
  <div class="form-group col-lg-3 col-md-3 col-sm-4 col-xs-12">
    <label class="form-control-label" for="port">Port:</label>
    <input class="form-control" type="text" name="port" value="7624">    
  </div>    
  
</form>
   
</div>

</div>

<script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.3/jquery.min.js"></script>
<script src="/static/js/bootstrap.min.js"></script>
</body>
</html>