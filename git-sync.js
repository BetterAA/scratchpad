(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.GitSync = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function cleanTitle(value) {
    return String(value == null ? "" : value).trim();
  }

  function isUntitled(value) {
    var title = cleanTitle(value);
    return !title || /^草稿\s*\d*$/.test(title) || title === "暂存";
  }

  function titleError(value) {
    var title = cleanTitle(value);
    if (isUntitled(title)) return "请先编辑标题";
    if (title === "." || title === "..") return "标题不能是路径名";
    if (/[\\/\u0000]/.test(title)) return "标题不能包含斜杠";
    for (var i = 0; i < title.length; i++) {
      if (title.charCodeAt(i) < 32 || title.charCodeAt(i) === 127) return "标题包含不可用字符";
    }
    return "";
  }

  function collectPushItems(tabs) {
    var items = [];
    var invalid = [];
    (tabs || []).forEach(function (tab, index) {
      var title = cleanTitle(tab && tab.title);
      var error = titleError(title);
      if (error) {
        invalid.push({ index: index, title: title || "（空标题）", error: error });
        return;
      }
      var item = { title: title, content: String(tab && tab.content || "") };
      var found = false;
      items.forEach(function (existing) {
        if (existing.title === title) {
          existing.content = item.content;
          found = true;
        }
      });
      if (!found) items.push(item);
    });
    return { items: invalid.length ? [] : items, invalid: invalid };
  }

  function mergePulledTabs(tabs, items, makeId) {
    var next = (tabs || []).map(function (tab) {
      return { id: tab.id, title: tab.title, content: tab.content };
    });
    var updated = 0;
    var added = 0;
    (items || []).forEach(function (item) {
      var matched = false;
      next.forEach(function (tab) {
        if (cleanTitle(tab.title) === item.title) {
          tab.content = item.content;
          matched = true;
          updated++;
        }
      });
      if (!matched) {
        next.push({ id: makeId(), title: item.title, content: item.content });
        added++;
      }
    });
    return { tabs: next, updated: updated, added: added };
  }

  function normalizeDays(value) {
    var days = parseInt(value, 10);
    if (!days || days < 1) days = 1;
    if (days > 3650) days = 3650;
    return days;
  }

  return {
    collectPushItems: collectPushItems,
    isUntitled: isUntitled,
    mergePulledTabs: mergePulledTabs,
    normalizeDays: normalizeDays,
  };
});
