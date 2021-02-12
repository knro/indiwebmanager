// Startup function
$(function()
{
    $('[data-toggle="tooltip"]').tooltip();

    loadCurrentProfileDrivers();
    getStatus();
    getIndihubStatus();

    $("#drivers_list").change(function() {
        var name = $("#profiles option:selected").text();
        saveProfileDrivers(name, true);
    });

    $("#remote_drivers").change(function() {
        var name = $("#profiles option:selected").text();
        saveProfileDrivers(name, true);
    });
});

function saveProfile() {
    var options = profiles.options;
    var name = options[options.selectedIndex].value;
    // Remove any extra spaces
    name = name.trim();

    var url = "api/profiles/" + name;

    //console.log(url)

    $.ajax({
        type: 'POST',
        url: encodeURI(url),
        success: function() {
            //console.log("add new a profile " + name);
            saveProfileDrivers(name);
        },
        error: function() {
            alert('error add new  profile failed');
        }
    });
}

function saveProfileInfo() {
    var options = profiles.options;
    var name = options[options.selectedIndex].value;
    console.log(name);
    var port = $("#profile_port").val();
    console.log(port);
    var autostart = ($('#profile_auto_start').is(':checked')) ? 1 : 0;
    var autoconnect = ($('#profile_auto_connect').is(':checked')) ? 1 : 0;
    //console.log(autostart);
    //var url     =  "api/profiles/" + name + "/" + port + "/" + autostart;
    var url = "api/profiles/" + name;

    var profileInfo = {
        "port": port,
        "autostart": autostart,
        "autoconnect": autoconnect,
    };
    profileInfo = JSON.stringify(profileInfo);
    console.log("Profile info " + profileInfo);

    console.log(url);

    $.ajax({
        type: 'PUT',
        url: encodeURI(url),
        data: profileInfo,
        contentType: "application/json; charset=utf-8",
        success: function() {
            console.log("Profile " + name + " info is updated");
        },
        error: function() {
            alert('error update profile info failed');
        }
    });
}

function saveProfileDrivers(profile, silent) {

    if (typeof(silent) === 'undefined') silent = false;

    var url = "api/profiles/" + profile + "/drivers";
    var drivers = [];

    $("#drivers_list :selected").each(function(i, sel) {
        drivers.push({
            "label": $(sel).text()
        });
    });

    // Check for remote drivers
    var remote = $("#remote_drivers").val();
    if (remote) {
        drivers.push({
            "remote": remote
        });
        console.log({
            "remote": remote
        });
    }

    drivers = JSON.stringify(drivers);

    //console.log("my json string is " + drivers);

    $.ajax({
        type: 'POST',
        url: encodeURI(url),
        data: drivers,
        contentType: "application/json; charset=utf-8",
        success: function() {
            //console.log("Drivers added successfully to profile");
            if (silent === false)
                $("#notify_message").html('<br/><div class="alert alert-success"><a href="#" class="close" data-dismiss="alert" aria-label="close">&times;</a>Profile ' + profile + ' saved.</div>');
        },
        error: function() {
            alert('error failed to add drivers to profile');
        }
    });
}

function loadCurrentProfileDrivers() {
    clearDriverSelection();

    var name = $("#profiles option:selected").text();
    var url = "api/profiles/" + name + "/labels";

    $.getJSON(url, function(drivers) {
        $.each(drivers, function(i, driver) {
            var label = driver.label;
            //console.log("Driver label is " + label);
            var selector = "#drivers_list [value='" + label + "']";
            $(selector).prop('selected', true);
        });

        $("#drivers_list").selectpicker('refresh');
    });

    url = encodeURI("api/profiles/" + name + "/remote");

    $.getJSON(url, function(data) {
        if (data && data.drivers !== undefined) {
            $("#remote_drivers").val(data.drivers);
        }
        else {
            $("#remote_drivers").val("");
        }
    });

    loadProfileData();

}

function loadProfileData() {
    var name = $("#profiles option:selected").text();
    var url = encodeURI("api/profiles/" + name);

    $.getJSON(url, function(info) {
        if (info.autostart == 1)
            $("#profile_auto_start").prop("checked", true);
        else
            $("#profile_auto_start").prop("checked", false);

        if (info.autoconnect == 1)
            $("#profile_auto_connect").prop("checked", true);
        else
            $("#profile_auto_connect").prop("checked", false);

        $("#profile_port").val(info.port);

    });
}

function clearDriverSelection() {
    $("#drivers_list option").prop('selected', false);
    $("#drivers_list").selectpicker('refresh');
    // Uncheck Auto Start
    $("#profile_auto").prop("checked", false);
    $("#profile_port").val("7624");
}

function addNewProfile() {
    var profile_name = $("#new_profile_name").val();
    if (profile_name) {
        //console.log("profile is " + profile_name);
        $("#profiles").append("<option id='" + profile_name + "' selected>" + profile_name + "</option>");

        clearDriverSelection();

        $("#notify_message").html('<br/><div class="alert alert-success"><a href="#" class="close" data-dismiss="alert" aria-label="close">&times;</a>Profile ' + profile_name + ' created. Select the profile drivers and then save the profile.</div>');
    }
}

function removeProfile() {
    //console.log("in delete profile");
    var name = $("#profiles option:selected").text();
    var url = "api/profiles/" + name;

    console.log(url);

    if ($("#profiles option").size() == 1) {
        $("#notify_message").html('<br/><div class="alert alert-success"><a href="#" class="close" data-dismiss="alert" aria-label="close">&times;</a>Cannot delete default profile.</div>');
        return;
    }

    $.ajax({
        type: 'DELETE',
        url: encodeURI(url),
        success: function() {
            //console.log("delete profile " + name);
            $("#profiles option:selected").remove();
            $("#profiles").selectpicker('refresh');
            loadCurrentProfileDrivers();

            $("#notify_message").html('<br/><div class="alert alert-success"><a href="#" class="close" data-dismiss="alert" aria-label="close">&times;</a>Profile ' + name + ' deleted.</div>');
        },
        error: function() {
            alert('error delete profile failed');
        }
    });
}

function toggleServer() {
    var status = $.trim($("#server_command").text());

    if (status == "Start") {
        var profile = $("#profiles option:selected").text();
        var url = "api/server/start/" + profile;

        $.ajax({
            type: 'POST',
            url: encodeURI(url),
            success: function() {
                //console.log("INDI Server started!");
                getStatus();
            },
            error: function() {
                alert('Failed to start INDI server.');
            }
        });
    } else {
        $.ajax({
            type: 'POST',
            url: "api/server/stop",
            success: function() {
                //console.log("INDI Server stopped!");
                getStatus();
                getIndihubStatus(); // when INDI-server stops - INDIHUB-agent stops as well
            },
            error: function() {
                alert('Failed to stop INDI server.');
            }
        });
    }
}

function changeAgentMode() {
    var mode = $("input[name='mode']:checked").val();
    $.ajax({
        type: 'POST',
        url: "api/indihub/mode/" + mode,
        success: function(data) {
            getIndihubStatus();
        },
        error: function(xhr, status, error) {
            alert('Failed to change INDIHUB Agent mode: ' + xhr.responseJSON.message);
            getIndihubStatus();
        }
    });
}

function getStatus() {
    $.getJSON("api/server/status", function(data) {
        if (data[0].status == "True")
            getActiveDrivers();
        else {
            $("#server_command").html("<span class='glyphicon glyphicon-cog' aria-hidden='true'></span> Start");
            $("#server_notify").html("<p class='alert alert-success'>Server is offline.</p>");
        }

    });
}

function getIndihubStatus() {
    $.ajax({
        type: "GET",
        url: "api/indihub/status",
        success: function(data) {
            if (data[0].status != "True") {
                $("#agent_notify").html("<p class='alert alert-success'>Agent is offline.</p>");
                $("#mode_off").prop('checked', true);
                return;
            }
            var msg = "<p class='alert alert-info'>Agent is Online in " + data[0].mode +"-mode</p>";
            $("#agent_notify").html(msg);
            $("#mode_"+ data[0].mode).prop('checked', true);

            // for share-mode: get extended status info with public endpoints
            if (data[0].mode == "share") {
                // optimistically - agent should be running and listening in no more than 3 sec
                // (users can always refresh the page to get Agent status loaded)
                setTimeout(getIndihubAgentStatus, 3000);
            }
        }
    });
}

function getIndihubAgentStatus() {
    $.ajax({
        type: "GET",
        url: "http://" + document.location.hostname + ":2020/status",
        success: function(data) {
            var msg = $("#agent_notify").html();
            if (data.mode == "share") {
                msg += "<ul>";
                for (var i = 0; i < data.publicEndpoints.length; i++) {
                    msg += "<li>" + data.publicEndpoints[i].name + ": <b>" + data.publicEndpoints[i].addr + "</b></li>";
                }
                msg += "</ul>";
            }
            $("#agent_notify").html(msg);
        },
        error: function(xhr, status, error) {
            alert("Could not load Agent data, please try to refresh the page!");
        }
    });
}

function getActiveDrivers() {
    $.getJSON("api/server/drivers", function(data) {
        $("#server_command").html("<span class='glyphicon glyphicon-cog' aria-hidden='true'></span> Stop");
        var msg = "<p class='alert alert-info'>Server is Online.<ul  class=\"list-unstyled\">";
        var counter = 0;
        $.each(data, function(i, field) {
            msg += "<li>" + "<button class=\"btn btn-xs\" " +
        "onCLick=\"restartDriver('" + field.label + "')\" data-toggle=\"tooltip\" " +
        "title=\"Restart Driver\">" +
        "<span class=\"glyphicon glyphicon-repeat\" aria-hidden=\"true\"></span></button> " +
        field.label + "</li>";
            counter++;
        });

        msg += "</ul></p>";

        $("#server_notify").html(msg);

        if (counter < $("#drivers_list :selected").size()) {
            $("#notify_message").html('<br/><div class="alert alert-success"><a href="#" class="close" data-dismiss="alert" aria-label="close">&times;</a>Not all profile drivers are running. Make sure all devices are powered and connected.</div>');
            return;
        }
    });

}


function restartDriver(label) {
        $.ajax({
            type: 'POST',
            url: "api/drivers/restart/" + label,
            success: function() {
                getStatus();
        $("#notify_message").html('<br/><div class="alert alert-success"><a href="#" class="close" data-dismiss="alert" aria-label="close">&times;</a>Restarting driver "' + label + '" succeeded.</div>');
            },
            error: function() {
                alert('Restarting driver "' + label + '" failed!');
            }
        });
 }

function rebootSystem() {
    if (!confirm("Please press OK to confirm remote system Reboot")) {
        return;
    }

    $.ajax({
        type: 'POST',
        url: "api/system/reboot",
        success: function(){
            $("#notify_system_message").html('<br/><div class="alert alert-success"><a href="#" class="close" data-dismiss="alert" aria-label="close">&times;</a>Reboot system succeeded.</div>');
        },
        error: function(){
            alert('Rebooting system failed!');
        }
    });
}

function poweroffSystem() {
    if (!confirm("Please press OK to confirm remote system Poweroff")) {
        return;
    }

    $.ajax({
        type: 'POST',
        url: "api/system/poweroff",
        success: function()
        {
            $("#notify_system_message").html('<br/><div class="alert alert-success"><a href="#" class="close" data-dismiss="alert" aria-label="close">&times;</a>Poweroff system succeeded.</div>');
        },
        error: function()
        {
            alert('Poweroff remote system failed!');
        }
    });
}
