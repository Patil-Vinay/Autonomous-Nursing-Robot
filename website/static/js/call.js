// Video call with the robot's display over WebRTC, signalling on /call/signal

(function () {
  const page = document.getElementById('call-page');
  const url = page.dataset.ws;
  const link = document.getElementById('link');
  const state = document.getElementById('state');
  const start = document.getElementById('start');
  const hang = document.getElementById('hang');
  const local = document.getElementById('local');
  const remote = document.getElementById('remote');

  // the ward network, no STUN or TURN server
  const config = { iceServers: [] };
  const RING_TIME = 45000;

  let pc = null;
  let stream = null;
  let callId = null;
  let ringTimer = null;
  let early = [];   // robot candidates that came before its answer

  const ros = new ROSLIB.Ros({ url: url });
  const signal = new ROSLIB.Topic({ ros: ros, name: '/call/signal', messageType: 'std_msgs/msg/String' });

  ros.on('connection', function () {
    link.textContent = 'Connected';
    link.className = 'chip ok';
    start.disabled = callId !== null;
  });
  ros.on('error', function () {});
  ros.on('close', function () {
    link.textContent = 'Robot offline';
    link.className = 'chip bad';
    start.disabled = true;
    setTimeout(function () { ros.connect(url); }, 3000);
  });

  function send(message) {
    message.call = callId;
    message.from = 'staff';
    signal.publish({ data: JSON.stringify(message) });
  }

  signal.subscribe(function (msg) {
    let m;
    try {
      m = JSON.parse(msg.data);
    } catch (e) {
      return;
    }
    if (m.from !== 'robot' || !pc || m.call !== callId) {
      return;
    }
    if (m.type === 'answer') {
      pc.setRemoteDescription({ type: 'answer', sdp: m.sdp }).then(function () {
        early.forEach(function (c) { pc.addIceCandidate(c); });
        early = [];
      });
      state.textContent = 'Connecting the video';
    } else if (m.type === 'candidate') {
      if (pc.remoteDescription) {
        pc.addIceCandidate(m.candidate);
      } else {
        early.push(m.candidate);
      }
    } else if (m.type === 'decline') {
      end(m.reason || 'The call was declined');
    } else if (m.type === 'hangup') {
      end('The call was ended at the robot');
    }
  });

  async function call() {
    start.disabled = true;
    state.textContent = 'Starting the camera';
    callId = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    } catch (e) {
      end('No camera or microphone: ' + e.message);
      return;
    }
    local.srcObject = stream;

    pc = new RTCPeerConnection(config);
    stream.getTracks().forEach(function (track) { pc.addTrack(track, stream); });
    pc.ontrack = function (e) { remote.srcObject = e.streams[0]; };
    pc.onicecandidate = function (e) {
      if (e.candidate) {
        send({ type: 'candidate', candidate: e.candidate.toJSON() });
      }
    };
    pc.onconnectionstatechange = function () {
      if (!pc) {
        return;
      }
      if (pc.connectionState === 'connected') {
        clearTimeout(ringTimer);
        state.textContent = 'In call';
      } else if (pc.connectionState === 'failed') {
        send({ type: 'hangup' });
        end('The connection was lost');
      }
    };

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    send({ type: 'offer', sdp: offer.sdp, name: page.dataset.name });
    hang.disabled = false;
    state.textContent = 'Ringing on the robot';
    ringTimer = setTimeout(function () {
      send({ type: 'hangup' });
      end('No answer');
    }, RING_TIME);
  }

  function end(text) {
    clearTimeout(ringTimer);
    if (pc) {
      pc.close();
    }
    if (stream) {
      stream.getTracks().forEach(function (track) { track.stop(); });
    }
    pc = null;
    stream = null;
    callId = null;
    early = [];
    local.srcObject = null;
    remote.srcObject = null;
    state.textContent = text;
    hang.disabled = true;
    start.disabled = !ros.isConnected;
  }

  start.addEventListener('click', call);
  hang.addEventListener('click', function () {
    send({ type: 'hangup' });
    end('Call ended');
  });
  window.addEventListener('beforeunload', function () {
    if (callId) {
      send({ type: 'hangup' });
    }
  });
})();
