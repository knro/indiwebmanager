// Startup function
$(function() {
    loadCurrentProfileDrivers();
    getStatus();

    $("#drivers_list").change(function() {
        var name = $("#profiles option:selected").text();
        saveProfileDrivers(name, true);
    });

    $("#custom_drivers").change(function() {
        var name = $("#profiles option:selected").text();
        saveProfileDrivers(name, true);
    });

});

function saveProfile() {
    var options = profiles.options;
    var name = options[options.selectedIndex].value;
    var url = "/api/profiles/" + name;

    //console.log(url)

    $.ajax({
        type: 'POST',
        url: url,
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
    var autostart = ($('#profile_auto').is(':checked')) ? 1 : 0;
    console.log(autostart);
    //var url     =  "/api/profiles/" + name + "/" + port + "/" + autostart;
    var url = "/api/profiles/" + name;

    var profileInfo = {
        "port": port,
        "autostart": autostart
    };
    profileInfo = JSON.stringify(profileInfo);
    console.log("Profile info " + profileInfo);

    console.log(url);

    $.ajax({
        type: 'PUT',
        url: url,
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

//function saveProfileDrivers(profile, silent=false)
function saveProfileDrivers(profile, silent) {

    if (typeof(silent) === 'undefined') silent = false;

    var url = "/api/profiles/" + profile + "/drivers";
    var drivers = [];

    $("#drivers_list :selected").each(function(i, sel) {
        drivers.push({
            "label": $(sel).text()
        });
    });

    // Check for custom drivers
    var custom = $("#custom_drivers").val();
    //console.log("custom drivers " + custom);
    if (custom) {
        drivers.push({
            "custom": custom
        });
        console.log({
            "custom": custom
        });
    }

    drivers = JSON.stringify(drivers);

    //console.log("my json string is " + drivers);

    $.ajax({
        type: 'POST',
        url: url,
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
    var url = "/api/profiles/" + name + "/labels";

    $.getJSON(url, function(drivers) {
        $.each(drivers, function(i, driver) {
            var label = driver.label;
            //console.log("Driver label is " + label);
            var selector = "#drivers_list [value='" + label + "']";
            $(selector).prop('selected', true);
        });

        $("#drivers_list").selectpicker('refresh');
    });

    url = "/api/profiles/" + name + "/custom";

    $.getJSON(url, function(drivers) {
        if (drivers) {
            drivers = drivers.drivers;
            $("#custom_drivers").val(drivers);
        }
    });

    loadProfileData();

}

function loadProfileData() {
    var name = $("#profiles option:selected").text();
    var url = "/api/profiles/" + name;

    $.getJSON(url, function(info) {
        if (info.autostart == 1)
            $("#profile_auto").prop("checked", true);
        else
            $("#profile_auto").prop("checked", false);

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
    var url = "/api/profiles/" + name;

    console.log(url);

    if ($("#profiles option").size() == 1) {
        $("#notify_message").html('<br/><div class="alert alert-success"><a href="#" class="close" data-dismiss="alert" aria-label="close">&times;</a>Cannot delete default profile.</div>');
        return;
    }

    $.ajax({
        type: 'DELETE',
        url: url,
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
        var url = "/api/server/start/" + profile;

        $.ajax({
            type: 'POST',
            url: url,
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
            url: "/api/server/stop",
            success: function() {
                //console.log("INDI Server stopped!");
                getStatus();
            },
            error: function() {
                alert('Failed to stop INDI server.');
            }
        });
    }
}

function getStatus() {
    $.getJSON("/api/server/status", function(data) {
        if (data[0].status == "True")
            getActiveDrivers();
        else {
            $("#server_command").html("<span class='glyphicon glyphicon-cog' aria-hidden='true'></span> Start");
            $("#server_notify").html("<p class='alert alert-success'>Server is offline.</p>");
        }

    });
}

function getActiveDrivers() {
    $.getJSON("/api/server/drivers", function(data) {
        $("#server_command").html("<span class='glyphicon glyphicon-cog' aria-hidden='true'></span> Stop");
        var msg = "<p class='alert alert-info'>Server is Online.<ul>";
        var counter = 0;
        $.each(data, function(i, field) {
            msg += "<li>" + field.driver + "</li>";
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
