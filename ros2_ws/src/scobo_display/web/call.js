// Video calls from the ward website over WebRTC, signalling on /call/signal

(function () {
  const box = document.getElementById('call');
  const text = document.getElementById('call-text');
  const buttons = document.getElementById('call-buttons');
  const local = document.getElementById('local');
  const remote = document.getElementById('remote');

  const config = { iceServers: [] };

  let pc = null;
  let stream = null;
  let offer = null;   // the call that is ringing or running
  let early = [];     // staff candidates that came before the answer

  const signal = new ROSLIB.Topic({ ros: ros, name: '/call/signal', messageType: 'std_msgs/msg/String' });

  function send(message) {
    message.call = offer.call;
    message.from = 'robot';
    signal.publish({ data: JSON.stringify(message) });
  }

  function setButtons(list) {
    buttons.replaceChildren();
    list.forEach(function (item) {
      const button = document.createElement('button');
      button.textContent = item[0];
      button.className = item[1];
      button.onclick = item[2];
      buttons.appendChild(button);
    });
  }

  signal.subscribe(function (msg) {
    let m;
    try {
      m = JSON.parse(msg.data);
    } catch (e) {
      return;
    }
    if (m.from !== 'staff') {
      return;
    }
    if (m.type === 'offer') {
      if (offer) {
        signal.publish({ data: JSON.stringify({ call: m.call, from: 'robot', type: 'decline', reason: 'The robot is already in a call' }) });
        return;
      }
      offer = m;
      early = [];
      ring();
    } else if (!offer || m.call !== offer.call) {
      return;
    } else if (m.type === 'candidate') {
      if (pc && pc.remoteDescription) {
        pc.addIceCandidate(m.candidate);
      } else {
        early.push(m.candidate);
      }
    } else if (m.type === 'hangup') {
      end();
    }
  });

  function ring() {
    box.hidden = false;
    box.className = 'ringing';
    text.textContent = (offer.name || 'The ward') + ' is calling';
    setButtons([['Answer', 'answer', answer], ['Decline', 'decline', decline]]);
  }

  function decline() {
    send({ type: 'decline', reason: 'The call was declined at the robot' });
    end();
  }

  async function answer() {
    setButtons([]);
    text.textContent = 'Connecting';
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    } catch (e) {
      send({ type: 'decline', reason: 'No camera or microphone on the robot' });
      end();
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
      if (pc && pc.connectionState === 'connected') {
        box.className = 'live';
        text.textContent = offer.name || 'The ward';
      } else if (pc && pc.connectionState === 'failed') {
        end();
      }
    };

    await pc.setRemoteDescription({ type: 'offer', sdp: offer.sdp });
    early.forEach(function (c) { pc.addIceCandidate(c); });
    early = [];
    const reply = await pc.createAnswer();
    await pc.setLocalDescription(reply);
    send({ type: 'answer', sdp: reply.sdp });
    setButtons([['Hang up', 'decline', function () { send({ type: 'hangup' }); end(); }]]);
  }

  function end() {
    if (pc) {
      pc.close();
    }
    if (stream) {
      stream.getTracks().forEach(function (track) { track.stop(); });
    }
    pc = null;
    stream = null;
    offer = null;
    early = [];
    local.srcObject = null;
    remote.srcObject = null;
    box.hidden = true;
    setButtons([]);
  }
})();
