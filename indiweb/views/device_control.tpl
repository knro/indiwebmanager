<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="viewport" content="width = device-width, initial-scale = 1">
  <title>{{device_name}} - INDI Control Panel</title>
  <link rel="stylesheet" type="text/css" href="/static/css/bootstrap.min.css">
  <link rel="stylesheet" type="text/css" href="/static/css/jquery-ui.min.css">
  <link rel="stylesheet" type="text/css" href="/static/css/schoolhouse.css">
  <link rel="stylesheet" type="text/css" href="/static/css/device_control.css">
</head>
<body>
  <div class="container-fluid">
    <div class="row">
      <div class="col-md-12">
        <h3>{{device_name}} Control Panel</h3>

        <!-- Device Status -->
        <div class="connection-controls">
          <div class="row">
            <div class="col-md-12">
              <div class="form-group">
                <label>Device Status:</label>
                <span id="device_status" class="label label-info">Loading...</span>
                <small class="text-muted" style="margin-left: 10px;">Properties update automatically</small>
              </div>
            </div>
          </div>
        </div>

        <!-- Property Groups Tabs -->
        <ul class="nav nav-tabs" id="property-tabs" role="tablist">
          <!-- Tabs will be populated dynamically -->
        </ul>

        <!-- Tab Content -->
        <div class="tab-content" id="property-tab-content">
          <!-- Tab content will be populated dynamically -->
        </div>

        <!-- Log Messages -->
        <div class="row">
          <div class="col-md-12">
            <div class="panel panel-default">
              <div class="panel-heading">
                <h4 class="panel-title">Device Messages</h4>
              </div>
              <div class="panel-body">
                <div id="device_messages" class="device-messages">
                  <p class="text-muted">No messages yet...</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script src="/static/js/jquery.min.js"></script>
  <script src="/static/js/bootstrap.min.js"></script>
  <script src="/static/js/jquery-ui.min.js"></script>
  <script>
    var deviceName = "{{device_name}}";
    var deviceStructure = {};
    var lastUpdateTime = Date.now();
    var messageLog = [];
    var maxMessages = 100;

    $(document).ready(function() {
      loadDeviceStructure();

      // Start polling for changes every 2 seconds
      setInterval(checkForUpdates, 2000);

      // Initialize message log
      addMessage("info", "Device control panel loaded", "System");
    });

    function loadDeviceStructure() {
      $("#device_status").removeClass("label-success label-warning label-danger")
                        .addClass("label-info")
                        .text("Loading...");

      $.getJSON("/api/devices/" + encodeURIComponent(deviceName) + "/structure", function(data) {
        console.log('Loaded device structure:', data);
        deviceStructure = data;
        buildPropertyDisplay();

        $("#device_status").removeClass("label-info label-danger")
                          .addClass("label-success")
                          .text("Connected - Auto-updating");
        addMessage("success", "Device structure loaded successfully", "System");
      }).fail(function(xhr, status, error) {
        console.error('Failed to load device structure:', error);
        $("#property-tab-content").html('<div class="alert alert-danger">Failed to load device structure. Make sure the device is connected and the INDI server is running.<br>Error: ' + (xhr.responseJSON?.detail || error) + '</div>');

        $("#device_status").removeClass("label-info label-success")
                          .addClass("label-danger")
                          .text("Error");
        addMessage("error", "Failed to load device structure: " + (xhr.responseJSON?.detail || error), "System");
      });
    }

    function checkForUpdates() {
      $.getJSON("/api/devices/" + encodeURIComponent(deviceName) + "/dirty", function(dirtyProps) {
        if (dirtyProps && dirtyProps.length > 0) {
          console.log('Dirty properties:', dirtyProps);
          fetchUpdatedProperties(dirtyProps);
        }
      }).fail(function(xhr, status, error) {
        console.error('Failed to check for updates:', error);
        addMessage("warning", "Connection check failed: " + error, "System");

        // If we get a 503 (service unavailable), try to reload the structure
        if (xhr.status === 503) {
          $("#device_status").removeClass("label-success")
                            .addClass("label-warning")
                            .text("Reconnecting...");
          addMessage("warning", "Device connection lost, attempting to reconnect...", "System");
          setTimeout(loadDeviceStructure, 5000);
        }
      });
    }

    function fetchUpdatedProperties(propertyNames) {
      $.ajax({
        type: 'POST',
        url: '/api/devices/' + encodeURIComponent(deviceName) + '/properties/batch',
        data: JSON.stringify({ properties: propertyNames }),
        contentType: 'application/json',
        success: function(updatedProps) {
          console.log('Updated properties:', updatedProps);
          updateProperties(updatedProps);
          addMessage("info", "Updated " + Object.keys(updatedProps).length + " properties", "System");
        },
        error: function(xhr, status, error) {
          console.error('Failed to fetch updated properties:', error);
          addMessage("error", "Failed to fetch property updates: " + error, "System");
        }
      });
    }

    function buildPropertyDisplay() {
      // Remember currently active tab
      var activeTabId = $("#property-tabs .active a").attr("href");
      var activeGroupName = null;
      if (activeTabId) {
        var tabId = activeTabId.substring(1); // Remove #
        activeGroupName = tabId.replace("tab-", "").replace(/-/g, " ");
      }

      // Create tabs for each group
      var tabsHtml = "";
      var contentHtml = "";
      var isFirst = true;
      var foundActiveTab = false;

      for (var groupName in deviceStructure) {
        var tabId = "tab-" + groupName.replace(/[^a-zA-Z0-9]/g, '-');
        var isActive = (activeGroupName === groupName) || (!foundActiveTab && isFirst);

        if (isActive) {
          foundActiveTab = true;
        }

        tabsHtml += '<li role="presentation"' + (isActive ? ' class="active"' : '') + '>' +
                   '<a href="#' + tabId + '" role="tab" data-toggle="tab">' + groupName + '</a></li>';

        contentHtml += '<div role="tabpanel" class="tab-pane' + (isActive ? ' active' : '') + '" id="' + tabId + '">';
        contentHtml += generateGroupContent(deviceStructure[groupName]);
        contentHtml += '</div>';

        isFirst = false;
      }

      $("#property-tabs").html(tabsHtml);
      $("#property-tab-content").html(contentHtml);
    }

    function updateProperties(updatedProps) {
      // Update the device structure with new property values
      for (var propName in updatedProps) {
        var updatedProp = updatedProps[propName];
        var groupName = updatedProp.group || "Main";

        if (deviceStructure[groupName] && deviceStructure[groupName][propName]) {
          var oldProp = deviceStructure[groupName][propName];

          // Log property changes for each element
          for (var elemName in updatedProp.elements) {
            var newElement = updatedProp.elements[elemName];
            var oldElement = oldProp.elements[elemName];

            var newValue = newElement.value;
            var oldValue = oldElement ? oldElement.value : null;

            if (oldValue !== newValue) {
              // For number properties, show formatted value in log if available
              var displayNewValue = newValue;
              var displayOldValue = oldValue;

              if (updatedProp.type === 'number') {
                displayNewValue = newElement.formatted_value || newValue;
                displayOldValue = (oldElement && oldElement.formatted_value) || oldValue;
              }

              logPropertyUpdate(propName, displayOldValue, displayNewValue, elemName);
            }
          }

          // Log state changes
          if (oldProp.state !== updatedProp.state) {
            addMessage("info", 'Property "' + propName + '" state changed: ' +
                      (oldProp.state || 'unknown') + ' → ' + updatedProp.state, deviceName);
          }

          // Update the property in our structure
          deviceStructure[groupName][propName] = updatedProp;

          // Update the UI elements for this property
          updatePropertyUI(propName, updatedProp);
        }
      }
    }

    function updatePropertyUI(propName, prop) {
      // Update individual property elements in the UI without rebuilding entire structure
      for (var elemName in prop.elements) {
        var element = prop.elements[elemName];
        var elemSelector = '[data-property="' + propName + '"][data-element="' + elemName + '"]';

        if (prop.type === 'text') {
          $(elemSelector).text(element.value || '');
        } else if (prop.type === 'number') {
          // Use formatted_value if available, otherwise fall back to value
          $(elemSelector).text(element.formatted_value || element.value || '');
        } else if (prop.type === 'switch') {
          // Update switch elements based on rule type
          var rule = prop.rule || 'OneOfMany';
          var isOn = element.value === 'On' || element.value === 'ON';

          if (rule === 'OneOfMany' || rule === 'AtMostOne') {
            // Update button group style
            var buttonSelector = '.switch-button[data-property="' + propName + '"][data-element="' + elemName + '"]';
            $(buttonSelector).removeClass('button-active button-inactive')
                           .addClass(isOn ? 'button-active' : 'button-inactive');
          } else if (rule === 'AnyOfMany') {
            // Update checkbox style
            var checkboxSelector = '.switch-checkbox[data-property="' + propName + '"][data-element="' + elemName + '"]';
            $(checkboxSelector).removeClass('checkbox-checked checkbox-unchecked')
                              .addClass(isOn ? 'checkbox-checked' : 'checkbox-unchecked');

            // Update status text
            var statusSelector = '.switch-status[data-property="' + propName + '"][data-element="' + elemName + '"]';
            $(statusSelector).removeClass('status-on status-off')
                            .addClass(isOn ? 'status-on' : 'status-off')
                            .text(element.value || 'Off');
          } else {
            // Fallback to original text update
            $(elemSelector).text(element.value || 'Off');
          }
        } else if (prop.type === 'light') {
          var lightSelector = '.light-indicator[data-property="' + propName + '"][data-element="' + elemName + '"]';
          $(lightSelector).removeClass('state-idle state-ok state-busy state-alert')
                         .addClass('state-' + (element.value || 'idle').toLowerCase());
        }
      }

      // Update property state indicator
      var stateSelector = '.property-state[data-property="' + propName + '"]';
      $(stateSelector).removeClass('state-idle state-ok state-busy state-alert')
                     .addClass('state-' + (prop.state || 'idle'));
    }

    function generateGroupContent(groupProperties) {
      var html = "";

      for (var propName in groupProperties) {
        var prop = groupProperties[propName];
        html += '<div class="property-item" id="prop-' + prop.name + '">';
        html += generatePropertyContent(prop);
        html += '</div>';
      }

      return html;
    }

    function generatePropertyContent(prop) {
      var html = '<div class="property-header">';
      html += '<span class="property-state state-' + (prop.state || 'idle') + '" data-property="' + prop.name + '"></span>';
      html += '<span class="property-label">' + (prop.label || prop.name) + '</span>';

      // Show type and rule information
      var typeInfo = prop.type;
      if (prop.type === 'switch' && prop.rule) {
        typeInfo += ' (' + prop.rule + ')';
      }
      html += '<small class="text-muted">(' + prop.name + ') - ' + typeInfo + '</small>';
      html += '</div>';

      if (prop.type === 'text') {
        html += generateTextProperty(prop);
      } else if (prop.type === 'number') {
        html += generateNumberProperty(prop);
      } else if (prop.type === 'switch') {
        html += generateSwitchProperty(prop);
      } else if (prop.type === 'light') {
        html += generateLightProperty(prop);
      }

      return html;
    }

    function generateTextProperty(prop) {
      var html = '<div class="property-elements">';
      for (var elemName in prop.elements) {
        var elem = prop.elements[elemName];
        html += '<div class="element-row">';
        html += '<span class="element-label">' + (elem.label || elemName) + ':</span>';
        html += '<span class="element-value" data-property="' + prop.name + '" data-element="' + elemName + '">';
        html += (elem.value || '(empty)');
        html += '</span>';
        html += '</div>';
      }
      html += '</div>';
      return html;
    }

    function generateNumberProperty(prop) {
      var html = '<div class="property-elements">';
      for (var elemName in prop.elements) {
        var elem = prop.elements[elemName];
        html += '<div class="element-row">';
        html += '<span class="element-label">' + (elem.label || elemName) + ':</span>';
        html += '<span class="element-value" data-property="' + prop.name + '" data-element="' + elemName + '">';
        // Use formatted_value if available, otherwise fall back to value
        html += (elem.formatted_value || elem.value || '0');
        html += '</span>';
        if (elem.format) {
          html += '<span class="text-muted"> (' + elem.format + ')</span>';
        }
        if (elem.min !== undefined && elem.max !== undefined) {
          html += '<small class="text-muted"> [' + elem.min + ' - ' + elem.max + ']</small>';
        }
        html += '</div>';
      }
      html += '</div>';
      return html;
    }

    function generateSwitchProperty(prop) {
      var html = '<div class="property-elements">';
      var rule = prop.rule || 'OneOfMany'; // Default to OneOfMany if not specified


      if (rule === 'OneOfMany') {
        // Button group style - only one button can be active
        html += '<div class="switch-group switch-button-group">';
        for (var elemName in prop.elements) {
          var elem = prop.elements[elemName];
          var isOn = elem.value === 'On' || elem.value === 'ON';
          console.log('Switch element:', elemName, 'value:', elem.value, 'type:', typeof elem.value, 'isOn:', isOn, 'rule:', rule);
          html += '<button type="button" class="switch-button ' + (isOn ? 'button-active' : 'button-inactive') + '" ';
          html += 'data-property="' + prop.name + '" data-element="' + elemName + '">';
          html += (elem.label || elemName);
          html += '</button>';
        }
        html += '</div>';
      } else if (rule === 'AtMostOne') {
        // Button group style - at most one button can be active
        html += '<div class="switch-group switch-button-group switch-optional">';
        for (var elemName in prop.elements) {
          var elem = prop.elements[elemName];
          var isOn = elem.value === 'On' || elem.value === 'ON';
          console.log('Switch element:', elemName, 'value:', elem.value, 'type:', typeof elem.value, 'isOn:', isOn, 'rule:', rule);
          html += '<button type="button" class="switch-button ' + (isOn ? 'button-active' : 'button-inactive') + '" ';
          html += 'data-property="' + prop.name + '" data-element="' + elemName + '">';
          html += (elem.label || elemName);
          html += '</button>';
        }
        html += '</div>';
      } else if (rule === 'AnyOfMany') {
        // Checkbox style - multiple can be selected
        html += '<div class="switch-group switch-checkbox-group">';
        for (var elemName in prop.elements) {
          var elem = prop.elements[elemName];
          var isOn = elem.value === 'On' || elem.value === 'ON';
          html += '<div class="switch-checkbox-item">';
          html += '<div class="switch-control">';
          html += '<span class="switch-checkbox ' + (isOn ? 'checkbox-checked' : 'checkbox-unchecked') + '" ';
          html += 'data-property="' + prop.name + '" data-element="' + elemName + '"></span>';
          html += '<span class="element-label">' + (elem.label || elemName) + '</span>';
          html += '</div>';
          html += '<span class="switch-status ' + (isOn ? 'status-on' : 'status-off') + '" ';
          html += 'data-property="' + prop.name + '" data-element="' + elemName + '">';
          html += (elem.value || 'Off');
          html += '</span>';
          html += '</div>';
        }
        html += '</div>';
      } else {
        // Fallback to original style for unknown rules
        html += '<div class="switch-group">';
        for (var elemName in prop.elements) {
          var elem = prop.elements[elemName];
          var isOn = elem.value === 'On' || elem.value === 'ON';
          html += '<span class="switch-element ' + (isOn ? 'switch-on' : 'switch-off') + '">';
          html += '<span class="element-label">' + (elem.label || elemName) + ':</span> ';
          html += '<strong data-property="' + prop.name + '" data-element="' + elemName + '">';
          html += (elem.value || 'Off');
          html += '</strong>';
          html += '</span>';
        }
        html += '</div>';
      }

      html += '</div>';
      return html;
    }

    function generateLightProperty(prop) {
      var html = '<div class="property-elements">';
      for (var elemName in prop.elements) {
        var elem = prop.elements[elemName];
        var lightClass = 'state-' + (elem.value || 'idle').toLowerCase();
        html += '<div class="element-row">';
        html += '<span class="light-indicator ' + lightClass + '" data-property="' + prop.name + '" data-element="' + elemName + '"></span>';
        html += '<span class="element-label">' + (elem.label || elemName) + ': </span>';
        html += '<span class="element-value" data-property="' + prop.name + '" data-element="' + elemName + '">';
        html += (elem.value || 'Unknown');
        html += '</span>';
        html += '</div>';
      }
      html += '</div>';
      return html;
    }

    function addMessage(type, message, source) {
      var timestamp = new Date();
      var messageObj = {
        timestamp: timestamp,
        type: type, // info, success, warning, error
        message: message,
        source: source || deviceName
      };

      messageLog.push(messageObj);

      // Limit to maxMessages
      if (messageLog.length > maxMessages) {
        messageLog.shift(); // Remove oldest message
      }

      updateMessageDisplay();
    }

    function updateMessageDisplay() {
      var messagesHtml = "";

      if (messageLog.length === 0) {
        messagesHtml = '<p class="text-muted">No messages yet...</p>';
      } else {
        for (var i = messageLog.length - 1; i >= 0; i--) { // Show newest first
          var msg = messageLog[i];
          var timeStr = formatTimestamp(msg.timestamp);
          var typeClass = "message-" + msg.type;

          messagesHtml += '<div class="message-entry ' + typeClass + '">';
          messagesHtml += '<span class="message-timestamp">' + timeStr + '</span>';
          messagesHtml += '<span class="message-source">[' + msg.source + ']</span>';
          messagesHtml += '<span class="message-text">' + msg.message + '</span>';
          messagesHtml += '</div>';
        }
      }

      $("#device_messages").html(messagesHtml);

      // Auto-scroll to bottom to show newest messages
      var messagesDiv = $("#device_messages")[0];
      messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    function formatTimestamp(timestamp) {
      var hours = timestamp.getHours().toString().padStart(2, '0');
      var minutes = timestamp.getMinutes().toString().padStart(2, '0');
      var seconds = timestamp.getSeconds().toString().padStart(2, '0');
      var ms = timestamp.getMilliseconds().toString().padStart(3, '0');

      return hours + ':' + minutes + ':' + seconds + '.' + ms;
    }

    function logPropertyUpdate(propName, oldValue, newValue, elementName) {
      var message;
      if (elementName) {
        message = 'Property "' + propName + '.' + elementName + '" changed: ' +
                 (oldValue || 'null') + ' → ' + (newValue || 'null');
      } else {
        message = 'Property "' + propName + '" updated';
      }
      addMessage("info", message, deviceName);
    }

    function logSwitchRuleInfo(propName, rule, elementName, newValue) {
      var ruleDesc = {
        'OneOfMany': 'button group selection',
        'AtMostOne': 'optional exclusive selection',
        'AnyOfMany': 'multiple selection allowed'
      };

      var message = 'Switch "' + propName + '.' + elementName + '" (' +
                   (ruleDesc[rule] || rule) + ') set to: ' + newValue;
      addMessage("info", message, deviceName);
    }

  </script>
</body>
</html>