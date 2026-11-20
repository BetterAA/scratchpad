(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TimerLogic = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function normalizeMinutes(value) {
    var mins = parseInt(value, 10);
    if (!mins || mins < 1) mins = 15;
    if (mins > 999) mins = 999;
    return mins;
  }

  function formatClock(totalSeconds) {
    var seconds = Math.floor(Math.abs(Number(totalSeconds) || 0));
    var minutes = Math.floor(seconds / 60);
    var remainder = seconds % 60;
    var prefix = Number(totalSeconds) < 0 ? "−" : "";
    return prefix + (minutes < 10 ? "0" : "") + minutes + ":" +
      (remainder < 10 ? "0" : "") + remainder;
  }

  function elapsedSeconds(durationSec, timeLeftSec) {
    return Math.max(0, Math.floor(durationSec - timeLeftSec));
  }

  function formatDuration(totalSeconds) {
    var seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
    var minutes = Math.floor(seconds / 60);
    return minutes + " 分 " + (seconds % 60) + " 秒";
  }

  function getPhase(timeLeftSec) {
    if (timeLeftSec < 0) return "overtime";
    if (timeLeftSec <= 60) return "low";
    return "running";
  }

  return {
    normalizeMinutes: normalizeMinutes,
    formatClock: formatClock,
    elapsedSeconds: elapsedSeconds,
    formatDuration: formatDuration,
    getPhase: getPhase,
  };
});
