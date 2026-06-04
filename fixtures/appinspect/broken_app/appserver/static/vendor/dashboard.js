// Intentional non-blocking warning: hotlinks a library from Splunk Web instead
// of embedding it. The demo's three red AppInspect failures are seeded in conf
// files so the failure count is deterministic.
require(['moment'], function (moment) {
  console.log('dashboard loaded at', moment().format());
});
