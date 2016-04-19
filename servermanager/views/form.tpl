<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">

  <!-- If IE use the latest rendering engine -->
  <meta http-equiv="X-UA-Compatible" content="IE=edge">

  <!-- Set the page to the width of the device and set the zoon level -->
  <meta name="viewport" content="width = device-width, initial-scale = 1">
  <title>INDI Server Manager</title>
  <link rel="stylesheet" type="text/css" href="/static/css/bootstrap.css">
  <link rel="stylesheet" type="text/css" href="/static/css/bootstrap-select.min.css">
  <link rel="stylesheet" type="text/css" href="/static/css/schoolhouse.css">
  
</head>
<body>

  <div class="container">

    <h2>INDI Server Manager</h2>
    <!-- <form> !-->

      <div id="firstrow" class="row">
       <div class="col-sm-6">            
        <div class="form-group">           
         <label>Equipment Profile:</label>
         <div class="input-group">
           <select onClick="loadCurrentProfileDrivers()" id="profiles" class="form-control">
%for profile in allProfiles:
    %if saved_profile == profile['name']:
        <option selected>{{profile['name']}}</option>
    %else:
        <option>{{profile['name']}}</option>
    %end
%end
           </select>              
           <span class="input-group-btn">
             <button class="btn btn-default" onCLick="saveProfile()" data-toggle="tooltip" title="Save Profile"><span class="glyphicon glyphicon-save" aria-hidden="true"></span></button>
             <button class="btn btn-default" onClick="removeProfile()" data-toggle="tooltip" title="Delete Profile"><span class="glyphicon glyphicon-minus" aria-hidden="true"></span></button>
           </span>
         </div>
       </div>
     </div>

     <div class="col-sm-6">
       <div class="form-group">             
         <label>New Profile:</label>
         <div class="input-group">
          <input class="form-control" id="new_profile_name" type="text" placeholder="New Profile">
          <span class="input-group-btn">
           <button id="add_profile" onClick="addNewProfile()" class="btn btn-default" data-toggle="tooltip" title="Add Profile"><span class="glyphicon glyphicon-plus" aria-hidden="true"></span></button>
          </span>
         </div>
     </div>
   </div> 
   </div>          

   <div class="row">
     <div class="col-sm-6">
     <div class="form-group">
     <label for="drivers" class="control-label">Drivers:</label>
       <select id="drivers_list" class="form-control selectpicker show-tick" data-live-search="true" title="Select drivers..." data-selected-text-format="count > 5" multiple>
%for family,drivers in sorted(allDrivers.items()):
       <optgroup label="{{family}}">
      %for driver in drivers:
        <option value="{{driver}}" data-tokens="{{driver}}">{{driver}}</option>
      %end
       </optgroup>
%end
       </select>
       </div>
     </div>
   
   <div class="row">
        <div class="col-sm-6">
            <div class="form-group">
            <label for="serverPort" class="control-label">Port:</label>
            <input class="form-control" id="server_port" type="text" value="{{port}}">
            </div>
        </div>    
    </div>
    
   </div>
      
    <div class="row">
        <div class="col-sm-6">
            <button id="server_command" onClick="toggleServer()" class="btn btn-default"><span class="glyphicon glyphicon-cog" aria-hidden="true"></span> Start</button>
        </div>
        <div class="col-sm-6">
            <label>Server Status</label>
            <div id="server_notify" class="well"></div>
        </div>
    </div>        
    
   </div>
</div>


<script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.3/jquery.min.js"></script>
<script src="/static/js/bootstrap.min.js"></script>
<script src="/static/js/bootstrap-select.min.js"></script>
<script src="/static/js/jquery-ui.min.js"></script>
<script src="/static/js/indi.js"></script>
</body>
</html>
