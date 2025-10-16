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

        <!-- Legend -->
        <div class="legend-section">
          <div class="row">
            <div class="col-md-6">
              <h5>Property Permissions</h5>
              <div class="legend-horizontal">
                <div class="legend-item">
                  <span class="legend-border property-readonly-border"></span>
                  <span>Read-only (grayish)</span>
                </div>
                <div class="legend-item">
                  <span class="legend-border property-readwrite-border"></span>
                  <span>Read-write</span>
                </div>
                <div class="legend-item">
                  <span class="legend-border property-writeonly-border"></span>
                  <span>Write-only</span>
                </div>
              </div>
            </div>
            <div class="col-md-6">
              <h5>Property States</h5>
              <div class="legend-horizontal">
                <div class="legend-item">
                  <span class="property-state state-idle"></span>
                  <span>Idle</span>
                </div>
                <div class="legend-item">
                  <span class="property-state state-ok"></span>
                  <span>OK</span>
                </div>
                <div class="legend-item">
                  <span class="property-state state-busy"></span>
                  <span>Busy</span>
                </div>
                <div class="legend-item">
                  <span class="property-state state-alert"></span>
                  <span>Alert</span>
                </div>
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
    var lastPollTime = Date.now() / 1000; // Track last poll timestamp in seconds
    var messageLog = [];
    var maxMessages = 100;
    var isConnected = true; // Track connection state
    var reconnectAttempts = 0;
    var maxReconnectAttempts = 10;
    var reconnectTimeout = null;

    $(document).ready(function() {
      loadDeviceStructure();

      // Start polling for changes every 1 second
      setInterval(checkForUpdates, 1000);

      // Initialize message log
      addMessage("info", "Device control panel loaded", "System");

      // Set up event handlers for copy and set buttons
      setupPropertyControls();
    });

    function loadDeviceStructure() {
      $("#device_status").removeClass("label-success label-warning label-danger")
                        .addClass("label-info")
                        .text("Loading...");

      $.getJSON("/api/devices/" + encodeURIComponent(deviceName) + "/structure", function(data) {
        console.log('Loaded device structure:', data);
        deviceStructure = data;
        buildPropertyDisplay();

        setConnectionState(true);
        addMessage("success", "Device structure loaded successfully", "System");
      }).fail(function(xhr, status, error) {
        console.error('Failed to load device structure:', error);
        $("#property-tab-content").html('<div class="alert alert-danger">Failed to load device structure. Make sure the device is connected and the INDI server is running.<br>Error: ' + (xhr.responseJSON?.detail || error) + '</div>');

        setConnectionState(false);
        addMessage("error", "Failed to load device structure: " + (xhr.responseJSON?.detail || error), "System");
      });
    }

    function checkForUpdates() {
      var currentTime = Date.now() / 1000;
      var pollUrl = "/api/devices/" + encodeURIComponent(deviceName) + "/poll?since=" + lastPollTime;

      $.getJSON(pollUrl, function(dirtyProps) {
        lastPollTime = currentTime; // Update poll timestamp

        // Connection is working - ensure we're in connected state
        if (!isConnected) {
          setConnectionState(true);
        }

        if (dirtyProps && dirtyProps.length > 0) {
          console.log('Dirty properties:', dirtyProps);
          fetchUpdatedProperties(dirtyProps);
        }
      }).fail(function(xhr, status, error) {
        console.error('Failed to check for updates:', error);
        addMessage("warning", "Connection check failed: " + error, "System");

        // Set disconnected state
        setConnectionState(false);

        // The automatic reconnection will be handled by setConnectionState(false)
      });
    }

    function setConnectionState(connected) {
      isConnected = connected;

      if (connected) {
        // Connection restored - reset reconnection state
        reconnectAttempts = 0;
        if (reconnectTimeout) {
          clearTimeout(reconnectTimeout);
          reconnectTimeout = null;
        }

        // Remove disconnected styling and re-enable controls
        $('body').removeClass('disconnected');
        $('.set-property-btn, .copy-value-btn, .switch-button, .switch-checkbox, .element-input').prop('disabled', false);

        $("#device_status").removeClass("label-warning label-danger")
                          .addClass("label-success")
                          .text("Connected - Auto-updating");
        addMessage("success", "Connection restored", "System");
      } else {
        // Add disconnected styling and disable all interactive controls
        $('body').addClass('disconnected');
        $('.set-property-btn, .copy-value-btn, .switch-button, .switch-checkbox, .element-input').prop('disabled', true);

        $("#device_status").removeClass("label-success label-info")
                          .addClass("label-danger")
                          .text("Disconnected");
        addMessage("error", "Connection lost - controls disabled", "System");

        // Start automatic reconnection attempts
        attemptReconnection();
      }
    }

    function attemptReconnection() {
      if (reconnectAttempts >= maxReconnectAttempts) {
        $("#device_status").text("Disconnected - Max retries reached");
        addMessage("error", "Maximum reconnection attempts reached. Please refresh the page.", "System");
        return;
      }

      reconnectAttempts++;
      var retryDelay = Math.min(5000 * reconnectAttempts, 30000); // Exponential backoff, max 30s

      $("#device_status").removeClass("label-danger")
                        .addClass("label-warning")
                        .text("Reconnecting... (attempt " + reconnectAttempts + "/" + maxReconnectAttempts + ")");

      addMessage("info", "Attempting reconnection #" + reconnectAttempts + " in " + (retryDelay/1000) + " seconds...", "System");

      reconnectTimeout = setTimeout(function() {
        loadDeviceStructure();
      }, retryDelay);
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
      var needsStructureReload = false;

      // Update the device structure with new property values
      for (var propName in updatedProps) {
        var updatedProp = updatedProps[propName];
        var groupName = updatedProp.group || "Main";

        if (deviceStructure[groupName] && deviceStructure[groupName][propName]) {
          var oldProp = deviceStructure[groupName][propName];

          // Check for CONNECTION property changes that might affect device structure
          if (propName === 'CONNECTION') {
            var oldConnectValue = oldProp.elements.CONNECT ? oldProp.elements.CONNECT.value : 'Off';
            var newConnectValue = updatedProp.elements.CONNECT ? updatedProp.elements.CONNECT.value : 'Off';

            if (oldConnectValue !== newConnectValue) {
              addMessage("info", 'Device connection changed: ' + oldConnectValue + ' → ' + newConnectValue, deviceName);
              needsStructureReload = true;
            }
          }

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

      // If CONNECTION changed, reload the entire device structure after a short delay
      // to allow new properties to be fully available
      if (needsStructureReload) {
        addMessage("info", "Device connection state changed, reloading device structure...", "System");
        setTimeout(function() {
          loadDeviceStructure();
        }, 1500); // Wait 1.5 seconds for device to fully connect/disconnect
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
            // Update button group style and remove blue clicked state
            var buttonSelector = '.switch-button[data-property="' + propName + '"][data-element="' + elemName + '"]';
            $(buttonSelector).removeClass('button-active button-inactive button-clicked')
                           .addClass(isOn ? 'button-active' : 'button-inactive');
          } else if (rule === 'AnyOfMany') {
            // Update checkbox style (horizontal layout doesn't have status text)
            var checkboxSelector = '.switch-checkbox[data-property="' + propName + '"][data-element="' + elemName + '"]';
            $(checkboxSelector).removeClass('checkbox-checked checkbox-unchecked')
                              .addClass(isOn ? 'checkbox-checked' : 'checkbox-unchecked');
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
        // Determine permission class
        var permClass = '';
        if (prop.perm === 'ro') {
          permClass = 'property-readonly';
        } else if (prop.perm === 'wo') {
          permClass = 'property-writeonly';
        } else if (prop.perm === 'rw') {
          permClass = 'property-readwrite';
        }

        html += '<div class="property-item ' + permClass + '" id="prop-' + prop.name + '">';
        html += generatePropertyContent(prop);
        html += '</div>';
      }

      return html;
    }

    function generatePropertyContent(prop) {
      // Determine permission class
      var permClass = '';
      if (prop.perm === 'ro') {
        permClass = 'property-readonly';
      } else if (prop.perm === 'wo') {
        permClass = 'property-writeonly';
      } else if (prop.perm === 'rw') {
        permClass = 'property-readwrite';
      }

      var html = '<div class="property-header">';
      html += '<span class="property-state state-' + (prop.state || 'idle') + '" data-property="' + prop.name + '"></span>';
      html += '<span class="property-label">' + (prop.label || prop.name) + '</span>';

      // Show type and rule information
      var typeInfo = prop.type;
      if (prop.type === 'switch' && prop.rule) {
        typeInfo += ' (' + prop.rule + ')';
      }
      html += '<small class="text-muted">(' + prop.name + ') - ' + typeInfo + '</small>';

      // Add info icon for switch properties with tooltip showing names and labels
      if (prop.type === 'switch') {
        var tooltipContent = '<div class="switch-tooltip-title">Switch elements in order:</div>';
        var elementIndex = 1;
        for (var elemName in prop.elements) {
          var elem = prop.elements[elemName];
          tooltipContent += '<div class="switch-tooltip-item">' + elementIndex + '. ' + (elem.label || elemName) + ' (Element ID: ' + elemName + ')</div>';
          elementIndex++;
        }
        html += '<span class="switch-info-icon" style="margin-left: 8px; cursor: help; color: #5bc0de; font-size: 16px;">';
        html += 'ⓘ';
        html += '<span class="switch-info-tooltip">' + tooltipContent + '</span>';
        html += '</span>';
      }

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
      var isWritable = (prop.perm === 'rw' || prop.perm === 'wo');

      for (var elemName in prop.elements) {
        var elem = prop.elements[elemName];
        html += '<div class="element-row">';
        html += '<span class="element-label" title="Element ID: ' + elemName + '">' + (elem.label || elemName) + ':</span>';

        if (isWritable) {
          // Writable property: current value + input controls
          html += '<div class="element-value-controls">';

          // For read-write properties, show current value and copy button
          if (prop.perm === 'rw') {
            html += '<span class="element-value element-current-value" data-property="' + prop.name + '" data-element="' + elemName + '">';
            html += (elem.value || '(empty)');
            html += '</span>';

            html += '<button type="button" class="btn btn-xs btn-default copy-value-btn" ';
            html += 'data-property="' + prop.name + '" data-element="' + elemName + '">↦</button>';
          }

          html += '<input type="text" class="form-control input-sm element-input" ';
          html += 'data-property="' + prop.name + '" data-element="' + elemName + '" ';
          html += 'placeholder="Enter text">';
          html += '</div>';
        } else {
          // Read-only property: just the value
          html += '<span class="element-value" data-property="' + prop.name + '" data-element="' + elemName + '">';
          html += (elem.value || '(empty)');
          html += '</span>';
        }

        html += '</div>';
      }

      // Add set button for writable properties (inline after last element)
      if (isWritable) {
        html += '<div class="element-row">';
        html += '<span class="element-label"></span>'; // Empty label for alignment
        html += '<div class="property-set-control">';
        html += '<button type="button" class="btn btn-sm btn-primary set-property-btn" ';
        html += 'data-property="' + prop.name + '">Set</button>';
        html += '</div>';
        html += '</div>';
      }

      html += '</div>';
      return html;
    }

    function generateNumberProperty(prop) {
      var html = '<div class="property-elements">';
      var isWritable = (prop.perm === 'rw' || prop.perm === 'wo');

      for (var elemName in prop.elements) {
        var elem = prop.elements[elemName];
        html += '<div class="element-row">';
        html += '<span class="element-label" title="Element ID: ' + elemName + '">' + (elem.label || elemName) + ':</span>';

        if (isWritable) {
          // Writable property: current value + input controls
          html += '<div class="element-value-controls">';

          // For read-write properties, show current value and copy button
          if (prop.perm === 'rw') {
            html += '<span class="element-value element-current-value" data-property="' + prop.name + '" data-element="' + elemName + '">';
            html += (elem.formatted_value || elem.value || '0');
            html += '</span>';
            if (elem.min !== undefined && elem.max !== undefined) {
              html += '<small class="text-muted"> [' + elem.min + ' - ' + elem.max + ']</small>';
            }

            html += '<button type="button" class="btn btn-xs btn-default copy-value-btn" ';
            html += 'data-property="' + prop.name + '" data-element="' + elemName + '">↦</button>';
          } else {
            // For write-only properties, show range info without current value
            if (elem.min !== undefined && elem.max !== undefined) {
              html += '<small class="text-muted"> [' + elem.min + ' - ' + elem.max + ']</small>';
            }
          }

          // Use text input for %m formatted fields to avoid spin controls
          var inputType = (elem.format && elem.format.includes('%m')) ? 'text' : 'number';
          html += '<input type="' + inputType + '" class="form-control input-sm element-input" ';
          html += 'data-property="' + prop.name + '" data-element="' + elemName + '" ';
          if (inputType === 'number') {
            if (elem.min !== undefined) html += 'min="' + elem.min + '" ';
            if (elem.max !== undefined) html += 'max="' + elem.max + '" ';
            if (elem.step !== undefined) html += 'step="' + elem.step + '" ';
          }
          html += 'placeholder="Enter value">';
          html += '</div>';
        } else {
          // Read-only property: just the value
          html += '<span class="element-value" data-property="' + prop.name + '" data-element="' + elemName + '">';
          html += (elem.formatted_value || elem.value || '0');
          html += '</span>';

          if (elem.min !== undefined && elem.max !== undefined) {
            html += '<small class="text-muted"> [' + elem.min + ' - ' + elem.max + ']</small>';
          }
        }

        html += '</div>';
      }

      // Add set button for writable properties (inline after last element)
      if (isWritable) {
        html += '<div class="element-row">';
        html += '<span class="element-label"></span>'; // Empty label for alignment
        html += '<div class="property-set-control">';
        html += '<button type="button" class="btn btn-sm btn-primary set-property-btn" ';
        html += 'data-property="' + prop.name + '">Set</button>';
        html += '</div>';
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
        // Checkbox style - multiple can be selected, display horizontally
        html += '<div class="switch-group switch-checkbox-group-horizontal">';
        for (var elemName in prop.elements) {
          var elem = prop.elements[elemName];
          var isOn = elem.value === 'On' || elem.value === 'ON';
          html += '<div class="switch-checkbox-item-horizontal">';
          html += '<span class="switch-checkbox ' + (isOn ? 'checkbox-checked' : 'checkbox-unchecked') + '" ';
          html += 'data-property="' + prop.name + '" data-element="' + elemName + '"></span>';
          html += '<span class="element-label" title="Element ID: ' + elemName + '">' + (elem.label || elemName) + '</span>';
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
          html += '<span class="element-label" title="Element ID: ' + elemName + '">' + (elem.label || elemName) + ':</span> ';
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
        html += '<span class="element-label" title="Element ID: ' + elemName + '">' + (elem.label || elemName) + ': </span>';
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
        for (var i = 0; i < messageLog.length; i++) { // Show oldest first, newest last
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

    function setupPropertyControls() {
      // Event delegation for copy value buttons
      $(document).on('click', '.copy-value-btn', function() {
        var propName = $(this).data('property');
        var elemName = $(this).data('element');
        var currentValueSpan = $('.element-current-value[data-property="' + propName + '"][data-element="' + elemName + '"]');
        var inputField = $('.element-input[data-property="' + propName + '"][data-element="' + elemName + '"]');

        var currentValue = currentValueSpan.text().trim();
        // Extract numeric value from formatted display if needed
        var numericValue = parseFloat(currentValue);
        if (!isNaN(numericValue)) {
          inputField.val(numericValue);
        } else {
          inputField.val(currentValue);
        }

        inputField.focus().select();
        addMessage("info", 'Copied current value "' + currentValue + '" to input field for ' + propName + '.' + elemName, "System");
      });

      // Event delegation for set property buttons
      $(document).on('click', '.set-property-btn', function() {
        var propName = $(this).data('property');
        var values = {};
        var hasValues = false;

        // Collect all input values for this property
        $('.element-input[data-property="' + propName + '"]').each(function() {
          var elemName = $(this).data('element');
          var value = $(this).val().trim();
          if (value !== '') {
            values[elemName] = value;
            hasValues = true;
          }
        });

        if (!hasValues) {
          addMessage("warning", "No values entered for property " + propName, "System");
          return;
        }

        // Send the values to the backend
        setPropertyValues(propName, values);
      });

      // Event delegation for switch button clicks
      $(document).on('click', '.switch-button', function() {
        var propName = $(this).data('property');
        var elemName = $(this).data('element');

        // Only handle clicks for writable properties
        var propertyItem = $(this).closest('.property-item');
        if (propertyItem.hasClass('property-readonly')) {
          return; // Ignore clicks on read-only switches
        }

        // Add blue clicked state
        $(this).addClass('button-clicked');

        // Determine the switch rule and handle accordingly
        var switchGroup = $(this).closest('.switch-button-group');
        var rule = 'OneOfMany'; // Default
        if (switchGroup.hasClass('switch-optional')) {
          rule = 'AtMostOne';
        }

        // Send switch update to backend
        setSwitchValue(propName, elemName, rule, $(this));
      });

      // Event delegation for switch checkbox clicks (AnyOfMany)
      $(document).on('click', '.switch-checkbox', function() {
        var propName = $(this).data('property');
        var elemName = $(this).data('element');

        // Only handle clicks for writable properties
        var propertyItem = $(this).closest('.property-item');
        if (propertyItem.hasClass('property-readonly')) {
          return; // Ignore clicks on read-only switches
        }

        // Toggle the checkbox state and send update
        var isCurrentlyChecked = $(this).hasClass('checkbox-checked');
        var newValue = isCurrentlyChecked ? 'Off' : 'On';

        // For AnyOfMany, just toggle this specific element
        var values = {};
        values[elemName] = newValue;

        addMessage("info", "Setting checkbox " + propName + "." + elemName + " to: " + newValue, "System");

        $.ajax({
          type: 'POST',
          url: '/api/devices/' + encodeURIComponent(deviceName) + '/properties/' + encodeURIComponent(propName) + '/set',
          data: JSON.stringify({ elements: values }),
          contentType: 'application/json',
          success: function(response) {
            addMessage("success", "Checkbox " + propName + "." + elemName + " set successfully", deviceName);
          },
          error: function(xhr, status, error) {
            var errorMsg = xhr.responseJSON?.detail || error;
            addMessage("error", "Failed to set checkbox " + propName + "." + elemName + ": " + errorMsg, "System");
          }
        });
      });
    }

    function setPropertyValues(propName, values) {
      addMessage("info", "Setting property " + propName + " with values: " + JSON.stringify(values), "System");

      $.ajax({
        type: 'POST',
        url: '/api/devices/' + encodeURIComponent(deviceName) + '/properties/' + encodeURIComponent(propName) + '/set',
        data: JSON.stringify({ elements: values }),
        contentType: 'application/json',
        success: function(response) {
          addMessage("success", "Property " + propName + " set successfully", deviceName);
          // Clear the input fields after successful set
          $('.element-input[data-property="' + propName + '"]').val('');
        },
        error: function(xhr, status, error) {
          var errorMsg = xhr.responseJSON?.detail || error;
          addMessage("error", "Failed to set property " + propName + ": " + errorMsg, "System");
        }
      });
    }

    function setSwitchValue(propName, elemName, rule, clickedButton) {
      var values = {};

      if (rule === 'OneOfMany') {
        // OneOfMany: Only one can be active, turn off all others
        values[elemName] = 'On';
        // Find all other elements in this property and set them to Off
        clickedButton.closest('.switch-button-group').find('.switch-button').each(function() {
          var otherElemName = $(this).data('element');
          if (otherElemName !== elemName) {
            values[otherElemName] = 'Off';
          }
        });
      } else if (rule === 'AtMostOne') {
        // AtMostOne: Can turn off current, or turn on and turn off others
        var isCurrentlyActive = clickedButton.hasClass('button-active');
        if (isCurrentlyActive) {
          // Turn off the currently active one
          values[elemName] = 'Off';
        } else {
          // Turn on this one and turn off all others
          values[elemName] = 'On';
          clickedButton.closest('.switch-button-group').find('.switch-button').each(function() {
            var otherElemName = $(this).data('element');
            if (otherElemName !== elemName && $(this).hasClass('button-active')) {
              values[otherElemName] = 'Off';
            }
          });
        }
      }

      addMessage("info", "Setting switch " + propName + " (" + rule + ") with values: " + JSON.stringify(values), "System");

      $.ajax({
        type: 'POST',
        url: '/api/devices/' + encodeURIComponent(deviceName) + '/properties/' + encodeURIComponent(propName) + '/set',
        data: JSON.stringify({ elements: values }),
        contentType: 'application/json',
        success: function(response) {
          addMessage("success", "Switch " + propName + " set successfully", deviceName);
        },
        error: function(xhr, status, error) {
          var errorMsg = xhr.responseJSON?.detail || error;
          addMessage("error", "Failed to set switch " + propName + ": " + errorMsg, "System");
          // Remove blue state on error
          clickedButton.removeClass('button-clicked');
        }
      });
    }

  </script>
</body>
</html>