// Robot page: ward plan or lidar map with the robot and its path, and the controls.
// Metres in the map frame, map y points up and canvas y points down.

(function () {
  const page = document.getElementById('robot-page');
  const url = page.dataset.ws;
  const canvas = document.getElementById('map');
  const ctx = canvas.getContext('2d');
  const link = document.getElementById('link');
  const reply = document.getElementById('reply');

  let grid = null;      // map info, plus the map drawn once at one pixel per cell
  let robot = null;     // {x, y, yaw}
  let path = [];
  let stops = [];       // beds 1 to 8, then home
  let occupied = {};
  const plan = JSON.parse(document.getElementById('ward-layout').textContent);
  const mapBox = canvas.parentElement;

  // floor plan or lidar map, remembered in this browser only
  let view = 'plan';
  try {
    view = localStorage.getItem('scobo-map-view') || 'plan';
  } catch (e) {}

  const ros = new ROSLIB.Ros({ url: url });

  ros.on('connection', function () {
    link.textContent = 'Connected';
    link.className = 'chip ok';
  });
  ros.on('error', function () {});
  ros.on('close', function () {
    link.textContent = 'Robot offline';
    link.className = 'chip bad';
    // roslib subscribes the topics again after a reconnect
    setTimeout(function () { ros.connect(url); }, 3000);
  });

  function topic(name, type, rate, callback) {
    new ROSLIB.Topic({ ros: ros, name: name, messageType: type, throttle_rate: rate })
      .subscribe(callback);
  }

  function yawOf(q) {
    return Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
  }

  topic('/map', 'nav_msgs/msg/OccupancyGrid', 0, function (msg) {
    const w = msg.info.width, h = msg.info.height;
    const cells = document.createElement('canvas');
    cells.width = w;
    cells.height = h;
    const c = cells.getContext('2d');
    const image = c.createImageData(w, h);
    for (let row = 0; row < h; row++) {
      for (let col = 0; col < w; col++) {
        const v = msg.data[row * w + col];
        const shade = v < 0 ? 226 : v > 50 ? 40 : 255;
        const i = ((h - 1 - row) * w + col) * 4;
        image.data[i] = image.data[i + 1] = image.data[i + 2] = shade;
        image.data[i + 3] = 255;
      }
    }
    c.putImageData(image, 0, 0);
    grid = { cells: cells, info: msg.info };
    draw();
  });

  topic('/robot_pose', 'geometry_msgs/msg/PoseStamped', 200, function (msg) {
    const p = msg.pose.position;
    robot = { x: p.x, y: p.y, yaw: yawOf(msg.pose.orientation) };
    document.getElementById('pose').textContent =
      'x ' + p.x.toFixed(1) + ' m, y ' + p.y.toFixed(1) + ' m';
    draw();
  });

  topic('/plan', 'nav_msgs/msg/Path', 1000, function (msg) {
    path = msg.poses.map(function (s) { return s.pose.position; });
    draw();
  });

  topic('/ward/bed_stops', 'geometry_msgs/msg/PoseArray', 0, function (msg) {
    stops = msg.poses.map(function (p) { return p.position; });
    draw();
  });

  topic('/ward/current_plan', 'scobo_interfaces/msg/WardPlan', 0, function (msg) {
    occupied = {};
    msg.beds.forEach(function (b) { occupied[b.number] = b.occupied; });
    document.querySelectorAll('[data-bed]').forEach(function (button) {
      const bed = Number(button.dataset.bed);
      button.classList.toggle('free', bed > 0 && !occupied[bed]);
    });
    draw();
  });

  topic('/ward/status', 'std_msgs/msg/String', 0, function (msg) {
    document.getElementById('status').textContent = msg.data;
    // a finished drive leaves the planned path behind
    if (!/^(Going|Visiting)/.test(msg.data)) {
      path = [];
      draw();
    }
  });

  // drawing, the view fills the canvas width

  function extent() {
    if (view === 'plan') {
      const r = plan.room;
      return { x0: r.x0 - 0.35, y0: r.y0 - 0.35, x1: r.x1 + 0.35, y1: r.y1 + 0.35 };
    }
    if (!grid) {
      return null;
    }
    const info = grid.info, o = info.origin.position;
    return { x0: o.x, y0: o.y, x1: o.x + info.width * info.resolution, y1: o.y + info.height * info.resolution };
  }

  function draw() {
    const width = canvas.clientWidth;
    const e = extent();
    if (!e || !width) {
      return;
    }
    const scale = width / (e.x1 - e.x0);
    const height = (e.y1 - e.y0) * scale;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.height = height + 'px';
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

    const px = function (x) { return (x - e.x0) * scale; };
    const py = function (y) { return height - (y - e.y0) * scale; };

    if (view === 'plan') {
      drawPlan(px, py, scale);
    } else {
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(grid.cells, 0, 0, width, height);
    }

    if (path.length > 1) {
      ctx.strokeStyle = '#0b7a75';
      ctx.lineWidth = 2.5;
      ctx.setLineDash([6, 5]);
      ctx.beginPath();
      path.forEach(function (p, i) {
        if (i === 0) {
          ctx.moveTo(px(p.x), py(p.y));
        } else {
          ctx.lineTo(px(p.x), py(p.y));
        }
      });
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // the plan shows the bed numbers on the beds, so its stops are plain dots
    ctx.font = '600 12px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    stops.forEach(function (p, i) {
      const home = i === stops.length - 1;
      const bed = i + 1;
      const free = !home && occupied[bed] === false;
      const small = view === 'plan' && !home;
      ctx.fillStyle = free ? '#b7c4cf' : home ? '#0f2a3a' : '#2563eb';
      ctx.beginPath();
      ctx.arc(px(p.x), py(p.y), small ? 5 : 11, 0, 2 * Math.PI);
      ctx.fill();
      if (!small) {
        ctx.fillStyle = '#fff';
        ctx.fillText(home ? 'H' : String(bed), px(p.x), py(p.y) + 0.5);
      }
    });

    if (robot) {
      const x = px(robot.x), y = py(robot.y);
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(-robot.yaw);
      ctx.fillStyle = '#0b7a75';
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(14, 0);
      ctx.lineTo(-9, 9);
      ctx.lineTo(-4, 0);
      ctx.lineTo(-9, -9);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }
  }

  // ward plan from the site: walls with the door, beds, lockers and furniture

  function drawPlan(px, py, scale) {
    const r = plan.room;

    function box(x, y, w, h) {
      ctx.beginPath();
      ctx.rect(px(x - w / 2), py(y + h / 2), w * scale, h * scale);
    }

    ctx.fillStyle = '#f7f9fb';
    box((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, r.x1 - r.x0, r.y1 - r.y0);
    ctx.fill();

    plan.lockers.forEach(function (l) {
      box(l.x, l.y, 0.5, 0.5);
      ctx.fillStyle = '#e3e9ee';
      ctx.fill();
      ctx.strokeStyle = '#b7c4cf';
      ctx.lineWidth = 1;
      ctx.stroke();
    });

    ctx.font = '500 11px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    plan.furniture.forEach(function (f) {
      box(f.x, f.y, f.w, f.h);
      ctx.fillStyle = '#e3e9ee';
      ctx.fill();
      ctx.strokeStyle = '#b7c4cf';
      ctx.lineWidth = 1;
      ctx.stroke();
      // labels go beside the piece, towards the middle of the room
      ctx.save();
      ctx.fillStyle = '#56677a';
      ctx.translate(px(f.x + f.w / 2) + 10, py(f.y));
      if (f.h > f.w * 2) {
        ctx.rotate(-Math.PI / 2);
        ctx.fillText(f.label, 0, 0);
      } else {
        ctx.textAlign = 'left';
        ctx.fillText(f.label, 0, 0);
      }
      ctx.restore();
    });

    const bw = plan.bed_size[0], bl = plan.bed_size[1];
    plan.beds.forEach(function (b) {
      const taken = b.number in occupied ? occupied[b.number] : b.occupied;
      const alert = taken && b.alert;
      // the head end is against the nearer long wall
      const head = b.y < (r.y0 + r.y1) / 2 ? -1 : 1;

      box(b.x, b.y, bw, bl);
      ctx.fillStyle = !taken ? 'rgba(0, 0, 0, 0)' : alert ? '#fff4e8' : '#ffffff';
      ctx.fill();
      ctx.setLineDash(taken ? [] : [5, 4]);
      ctx.strokeStyle = !taken ? '#b7c4cf' : alert ? '#c2410c' : '#8aa2b2';
      ctx.lineWidth = alert ? 2 : 1.5;
      ctx.stroke();
      ctx.setLineDash([]);

      if (taken) {
        box(b.x, b.y + head * (bl / 2 - 0.25), bw - 0.2, 0.3);
        ctx.fillStyle = alert ? '#fde3c8' : '#e6edf2';
        ctx.fill();
      }

      ctx.fillStyle = taken ? '#15232d' : '#8a9aa8';
      ctx.font = '700 15px "Plus Jakarta Sans", Inter, sans-serif';
      ctx.fillText(String(b.number), px(b.x), py(b.y) - 7);
      ctx.font = '500 11px Inter, sans-serif';
      ctx.fillStyle = '#56677a';
      ctx.fillText(taken ? (b.initials || '') : 'Free', px(b.x), py(b.y) + 10);

      if (alert) {
        const bx = px(b.x + bw / 2), by = py(b.y - head * bl / 2);
        ctx.fillStyle = '#c2410c';
        ctx.beginPath();
        ctx.arc(bx, by, 9, 0, 2 * Math.PI);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.font = '700 12px Inter, sans-serif';
        ctx.fillText('!', bx, by + 0.5);
      }
    });

    // walls, open at the door on the east side
    const d = plan.door;
    ctx.strokeStyle = '#15232d';
    ctx.lineWidth = Math.max(3, 0.1 * scale);
    ctx.lineJoin = 'miter';
    ctx.beginPath();
    ctx.moveTo(px(r.x1), py(d.y1));
    ctx.lineTo(px(r.x1), py(r.y1));
    ctx.lineTo(px(r.x0), py(r.y1));
    ctx.lineTo(px(r.x0), py(r.y0));
    ctx.lineTo(px(r.x1), py(r.y0));
    ctx.lineTo(px(r.x1), py(d.y0));
    ctx.stroke();

    ctx.save();
    ctx.fillStyle = '#56677a';
    ctx.font = '500 11px Inter, sans-serif';
    ctx.translate(px(r.x1) - 12, py((d.y0 + d.y1) / 2));
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Door', 0, 0);
    ctx.restore();
  }

  document.querySelectorAll('[data-view]').forEach(function (button) {
    button.classList.toggle('on', button.dataset.view === view);
    button.addEventListener('click', function () {
      view = button.dataset.view;
      try {
        localStorage.setItem('scobo-map-view', view);
      } catch (e) {}
      document.querySelectorAll('[data-view]').forEach(function (b) {
        b.classList.toggle('on', b === button);
      });
      mapBox.classList.toggle('plan', view === 'plan');
      draw();
    });
  });
  mapBox.classList.toggle('plan', view === 'plan');

  window.addEventListener('resize', draw);
  draw();

  // controls, only on the page for nurses

  function call(name, type, request) {
    reply.textContent = 'Sending...';
    new ROSLIB.Service({ ros: ros, name: name, serviceType: type }).callService(
      new ROSLIB.ServiceRequest(request),
      function (res) { reply.textContent = res.message; },
      function (error) { reply.textContent = 'No answer from the robot: ' + error; });
  }

  document.querySelectorAll('[data-bed]').forEach(function (button) {
    button.addEventListener('click', function () {
      call('/ward/go_to', 'scobo_interfaces/srv/GoTo', { bed: Number(button.dataset.bed) });
    });
  });

  const stop = document.getElementById('stop');
  if (stop) {
    stop.addEventListener('click', function () {
      call('/ward/stop', 'std_srvs/srv/Trigger', {});
    });
    document.getElementById('run-now').addEventListener('click', function () {
      call('/ward/run_now', 'std_srvs/srv/Trigger', {});
    });
  }
})();
