const heartbeat = setInterval(() => {
  process.stdout.write("child:tick\n");
}, 250);

process.stdout.write(`child:ready:${process.pid}\n`);

function shutdown() {
  clearInterval(heartbeat);
  process.stdout.write("child:shutdown\n");
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
