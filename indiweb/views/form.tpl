% import socket
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">

  <!-- If IE use the latest rendering engine -->
  <meta http-equiv="X-UA-Compatible" content="IE=edge">

  <!-- Set the page to the width of the device and set the zoon level -->
  <meta name="viewport" content="width = device-width, initial-scale = 1">
  <title>{{hostname}} INDI Web Manager</title>
  <link rel="stylesheet" type="text/css" href="static/css/bootstrap.min.css">
  <link rel="stylesheet" type="text/css" href="static/css/jquery-ui.min.css">
  <link rel="stylesheet" type="text/css" href="static/css/bootstrap-select.min.css">
  <link rel="stylesheet" type="text/css" href="static/css/schoolhouse.css">
  <style>
      .notbold{
          font-weight:normal
      }
  </style>
</head>
<body>

  <div class="container">

    <h4>{{hostname}} INDI Web Manager</h4>
    <!-- <form> !-->

      <div id="firstrow" class="row">
       <div class="col-sm-6">
        <div class="form-group">
         <label>Equipment Profile:</label>
         <div class="input-group">
           <select onchange="loadCurrentProfileDrivers()" id="profiles" class="form-control">
%for profile in profiles:
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
		<div>
		    <label class="checkbox-inline"><input id="profile_auto_start" onChange="saveProfileInfo()" type="checkbox" value="Autostart">Auto Start</label>
		    <label class="checkbox-inline"><input id="profile_auto_connect" onChange="saveProfileInfo()" type="checkbox" value="Autoconnect">Auto Connect</label>
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
%for family,driver_list in sorted(drivers.items()):
       <optgroup label="{{family}}">
      %for driver in driver_list:
        <option value="{{driver}}" data-tokens="{{driver}}">{{driver}}</option>
      %end
       </optgroup>
%end
       </select>
       </div>
     </div>

        <div class="col-sm-6">
            <div class="form-group">
            <label for="serverPort" class="control-label">Port:</label>
            <input id="profile_port" onChange="saveProfileInfo()" class="form-control" type="text" value="7624">
            </div>
        </div>

   </div>

     <div class="row">
        <div class="col-sm-6">
            <div class="form-group">
                <label for="remoteDrivers" class="control-label">Remote Drivers:</label>
                <input class="form-control" id="remote_drivers" type="text" placeholder="driver1@remotehost,driver2@remotehost">
            </div>

            <button id="server_command" onClick="toggleServer()" class="btn btn-default"><span class="glyphicon glyphicon-cog" aria-hidden="true"></span> Start</button>
            <div id="notify_message"></div>
        </div>
        <div class="col-sm-6">
            <div class="form-group">
                <label>Server Status</label>
                <div id="server_notify" class="well"></div>
            </div>
        </div>
    </div>

    <div class="row">
        <div class="col-sm-6">
            <div class="form-group">
                <label class="control-label">Poweroff Reboot:</label>
                <button id="system_reboot" onClick="rebootSystem()" class="btn btn-default" data-toggle="tooltip" title="Reboot remote System"><span class="glyphicon glyphicon-repeat" aria-hidden="true"></span></button>
                <button id="system_poweroff" onClick="poweroffSystem()" class="btn btn-default" data-toggle="tooltip" title="PowerOff remote System"><span class="glyphicon glyphicon-off" aria-hidden="true"></span></button>
                <div id="notify_system_message"></div>
            </div>
        </div>
    </div>
  </div>

  <br />
  <br />

  <div class="container">
    <h4>INDIHUB Network Agent Control <a href="https://indihub.space" target="_blank"><span class="glyphicon glyphicon-info-sign" aria-hidden="true"></span></a></h4>
    <div class="row">
      <div class="col-sm-6">
          <label>Agent Mode:</label>
          <div class="form-check">
              <span data-toggle="tooltip" title="Agent is not running">
                  <input class="form-check-input" type="radio" name="mode" id="mode_off" value="off" checked>
                  <label class="form-check-label" for="mode_off">
                      Off
                  </label>
              </span>
          </div>
          <div class="form-check">
              <span data-toggle="tooltip" title="Equipment sharing is not available, contribute images">
                  <input class="form-check-input" type="radio" name="mode" id="mode_solo" value="solo">
                  <label class="form-check-label" for="mode_solo">
                      Solo
                  </label>
              </span>
          </div>
          <div class="form-check">
              <span data-toggle="tooltip" title="Share your equipment and open remote access to your guests">
                  <input class="form-check-input" type="radio" name="mode" id="mode_share" value="share">
                  <label class="form-check-label" for="mode_share">
                      Share
                  </label>
              </span>
          </div>
          <div class="form-check">
              <span data-toggle="tooltip" title="Your equipment is operated by smart scheduler in the cloud">
                  <input class="form-check-input" type="radio" name="mode" id="mode_robotic" value="robotic">
                  <label class="form-check-label" for="mode_robotic">
                      Robotic
                  </label>
              </span>
          </div>
          <button id="agent_command" onClick="changeAgentMode()" class="btn btn-default"><span class="glyphicon glyphicon-cog" aria-hidden="true"></span> Change Mode</button>
      </div>
      <div class="col-sm-6">
        <div class="form-group">
          <label>Agent Status</label>
          <div id="agent_notify" class="well">Off</div>
        </div>
      </div>
    </div>
  </div>


<script src="static/js/jquery.min.js"></script>
<script src="static/js/bootstrap.min.js"></script>
<script src="static/js/bootstrap-select.min.js"></script>
<script src="static/js/jquery-ui.min.js"></script>
<script src="static/js/indi.js"></script>
</body>
</html>
