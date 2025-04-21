$(document).ready(function () {
  // Fetch and display playlists
  fetchPlaylists();
  // Handle form submission
  $("#prompt-form").submit(function (event) {
    event.preventDefault();
    sendMessage();
  });
  // Handle Enter key press in textarea
  $("#prompt").keypress(function (event) {
    if (event.which === 13 && !event.shiftKey) {
      event.preventDefault();
      $("#prompt-form").submit();
    }
  });
  // Handle playlist selection
  $("#playlist-dropdown").change(function () {
    var playlistId = $(this).val();
    // if (playlistId !== 'create-new') {
    //     fetchPlaylistTracks(playlistId, function(playlistContext) {
    //         loadConversation(playlistId, playlistContext);
    //     });
    // } else {
    //     $('#playlist-tracks').empty();
    //     $('#total-tracks').text('0');
    //     $('#total-duration').text('0:00');
    //     $('#playlist-context').val('');
    //     $('#conversation').empty();
    // }
    fetchPlaylistTracks(playlistId, function (playlistContext) {
      loadConversation(playlistId, playlistContext);
    });
  });

  // Draggable separator
  const separator = document.querySelector(".separator");
  let isDragging = false;

  separator.addEventListener("mousedown", function (e) {
    isDragging = true;
    document.body.style.cursor = "col-resize";
  });

  document.addEventListener("mouseup", function (e) {
    isDragging = false;
    document.body.style.cursor = "default";
  });

  document.addEventListener("mousemove", function (e) {
    if (isDragging) {
      const container = document.querySelector(".container");
      const leftPanel = document.querySelector(".chat-panel");
      const rightPanel = document.querySelector(".playlist-panel");
      const containerRect = container.getBoundingClientRect();
      const newLeftPanelWidth = e.clientX - containerRect.left;

      if (newLeftPanelWidth > 100 && newLeftPanelWidth < containerRect.width - 100) {
        leftPanel.style.width = newLeftPanelWidth + "px";
        rightPanel.style.width = containerRect.width - newLeftPanelWidth - separator.offsetWidth + "px";
      }
    }
  });

  function fetchPlaylists() {
    $.get("/playlists", function (data) {
      $("#playlist-dropdown").empty();
      // $('#playlist-dropdown').append('<option value="create-new">Create New</option>');
      data.playlists.forEach(function (playlist) {
        //TODO: Sort Public, private, collaboratively and alphabetically in the sections

        icon = playlist.public ? "&#127760;" : "&#x1F512;";
        //icon = playlist.public ? '<i class="fa-thin fa-globe"></i>' : '<i class="fa-thin fa-lock"></i>'

        if (playlist.owner.id == $("#user_id").text()) {
          $("#playlist-dropdown").append(`<option value="${playlist.id}">${icon} ${playlist.name}</option>`);
        }
      });
    });
  }

  function fetchPlaylistTracks(playlistId, callback) {
    console.log("fetching Playlist Tracks:", playlistId);

    $.get("/playlist_tracks/" + playlistId, function (data) {
      $("#playlist-url").attr("href", "https://open.spotify.com/playlist/" + playlistId);
      $("#playlist-tracks").empty();

      var playlistContext = "";
      data.tracks.forEach(function (track) {
        console.log("tracks:", track.name);

        $("#playlist-tracks").append(
          `<div class="track">
            <div class="track-number"> ${track.idx} </div>
            <div class="track-duration-from-start"> ${track.duration_from_start} </div>
            <img src="${track.album_image_url}" alt="Album Art" width="50">
            <div class="track-info">
                <div class="track-name">${track.name}</div>
                <div class="track-artist">${track.author}</div>
                <div class="track-duration">${track.duration}</div>
                <!-- div class="track-album">${track.album}</div -->
        </div>`
        );
        playlistContext += "Track " + track.idx + ": " + track.name + " by " + track.author + " from the album " + track.album + " (" + track.duration + ").\n";
      });
      $("#total-tracks").text(data.total_tracks);
      $("#total-duration").text(data.total_duration);
      $("#playlist-context").val(playlistContext);
      if (callback) {
        callback(playlistContext);
      }
    });
  }

  function loadConversation(playlistId, playlistContext) {
    $.get("/conversation/" + playlistId, function (data) {
      //$.get('/conversation', { conversation_name: playlistId }, function(data) {
      $("#conversation").empty();

      if (data.conversation.length === 0) {
        $("#conversation").append('<div class="message bot">No previous conversation found for this playlist.</div>');
      } else {
        data.conversation.forEach(function (message) {
          var messageClass = message.role === "user" ? "message user" : "message bot";
          $("#conversation").append(`<div class="${messageClass}"> ${message.content} </div>`);
        });
      }
      // Update the context with the current playlist content
      $("#playlist-context").val(playlistContext);
    });
  }

  function sendMessage() {
    var prompt = $("#prompt").val();
    var conversationName = $("#playlist-dropdown").val();
    var playlistContext = $("#playlist-context").val();
    $("#spinner").show();
    $.post(
      "/send_message",
      {
        prompt: prompt,
        conversation_name: conversationName,
        playlist_context: playlistContext,
      },
      function (data) {
        $("#spinner").hide();
        $("#conversation").append(`<div class="message user">${prompt}</div>`);
        $("#conversation").append(`<div class="message bot">${data.response}</div>`);
        $("#prompt").val("");
      }
    ).fail(function () {
      $("#spinner").hide();
      alert("Failed to get response from server.");
    });
  }

  $("#apply-button").click(function () {
    alert("Apply button clicked");
    var conversationName = $("#playlist-dropdown").val();
    var playlistContext = $("#playlist-context").val();
    var lastMessage = $("#conversation .message.bot:last").text();
    $("#spinner").show();
    $.post("/apply_proposal", { proposal: lastMessage, conversation_name: conversationName, playlist_context: playlistContext }, function (data) {
      $("#spinner").hide();
      $("#conversation").append(`<div class="message bot">${data.response}</div>`);
      fetchPlaylistTracks(conversationName, function (playlistContext) {
        var playlistContext = $("#playlist-context").val();
        loadConversation(conversationName, playlistContext);
      });
    });
  });

  $("#clear-conversation-button").click(function () {
    alert("Clear conversation button clicked");
    var conversationName = $("#playlist-dropdown").val();
    $.ajax({
      url: "/conversation/" + conversationName,
      type: "DELETE",
      success: function (result) {
        $("#conversation").empty();
        $("#playlist-context").val("");
        loadConversation(conversationName, "");
      },
    });
  });


}); // end of document ready
