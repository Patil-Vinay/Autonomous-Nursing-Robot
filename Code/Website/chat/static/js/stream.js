const localVideoContainer = document.getElementById('localVideoContainer');
const remoteVideoContainer = document.getElementById('remoteVideoContainer');
const muteAudioBtn = document.getElementById('muteAudio');
const muteVideoBtn = document.getElementById('muteVideo');

// Contains Audio and Video Track of Local User
let localTracks = [];
let client = null;

let getAppId = async () => {
    const response = await fetch('/get_app_id/');
    const data = await response.json();
    return data.app_id;
}

let joinAndDisplayLocalStream = async () => {
    const APP_ID = await getAppId();
    const CHANNEL = 'main';
    let TOKEN = sessionStorage.getItem('token');
    let uid = Number(sessionStorage.getItem('uid'));
    client = AgoraRTC.createClient({mode: 'rtc', codec: 'vp8'});

    client.on('user-published', handleUserJoined)
    try {
      await client.join(APP_ID, CHANNEL, TOKEN, uid)
    } catch(error) {
        window.open('/join/', '_self')
    }
    localTracks = await AgoraRTC.createMicrophoneAndCameraTracks()
    localTracks[1].play('localVideoContainer')
    await client.publish(localTracks)
}

let handleUserJoined = async (user, mediaType) => {
    await client.subscribe(user, mediaType)
    if (mediaType === 'video') {
        user.videoTrack.play(remoteVideoContainer)
    }
    if (mediaType === 'audio') {
        user.audioTrack.play();
    }
}

let endCall = async () => {
    for (let i=0; i<localTracks.length; i++) {
        localTracks[i].stop()
        localTracks[i].close()
    }
    await client.leave()
    window.open('/join/', '_self')
}

let toggleCamera = async (e)=> {
    if (localTracks[1].muted) {
        await localTracks[1].setMuted(false)
        muteVideoBtn.style.backgroundColor = '#BcBbB8'
    } else {
        await localTracks[1].setMuted(true)
        muteVideoBtn.style.backgroundColor = '#fff'
    }
}

let toggleMic = async (e)=> {
    if (localTracks[0].muted) {
        await localTracks[0].setMuted(false)
        muteAudioBtn.style.backgroundColor = '#BcBbB8'
    } else {
        await localTracks[0].setMuted(true)
        muteAudioBtn.style.backgroundColor = '#fff'
    }
}

document.getElementById('hangUp').addEventListener('click', endCall)
muteVideoBtn.addEventListener('click', toggleCamera)
muteAudioBtn.addEventListener('click', toggleMic)


joinAndDisplayLocalStream()
