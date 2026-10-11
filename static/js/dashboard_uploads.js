(function () {
  "use strict";

  document.querySelectorAll("[data-upload-input]").forEach(function (input) {
    var dropzone = input.closest("[data-upload-dropzone]");
    var filename = dropzone.querySelector("[data-upload-filename]");
    var preview = dropzone.querySelector("img[data-upload-preview]");
    var previewUrl = null;

    function showFile(file) {
      if (!file) {
        filename.textContent = "Choose a file or drag it here";
        if (preview) {
          preview.hidden = true;
          preview.removeAttribute("src");
        }
        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
          previewUrl = null;
        }
        return;
      }

      filename.textContent = file.name;
      if (preview && file.type.indexOf("image/") === 0) {
        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
        }
        previewUrl = URL.createObjectURL(file);
        preview.src = previewUrl;
        preview.hidden = false;
      } else if (preview) {
        preview.hidden = true;
        preview.removeAttribute("src");
        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
          previewUrl = null;
        }
      }
    }

    input.addEventListener("change", function () {
      showFile(input.files[0]);
    });

    ["dragenter", "dragover"].forEach(function (eventName) {
      dropzone.addEventListener(eventName, function (event) {
        event.preventDefault();
        dropzone.classList.add("is-dragging");
      });
    });

    ["dragleave", "drop"].forEach(function (eventName) {
      dropzone.addEventListener(eventName, function (event) {
        event.preventDefault();
        dropzone.classList.remove("is-dragging");
      });
    });

    dropzone.addEventListener("drop", function (event) {
      var file = event.dataTransfer.files[0];
      if (!file) {
        return;
      }
      var transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
      showFile(file);
    });
  });
})();
