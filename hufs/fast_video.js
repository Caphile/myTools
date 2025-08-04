document.querySelector('#video-div > iframe').src = 'https://howtovideos.hosted.panopto.com/Panopto/Pages/Embed.aspx?id=8c2b2fcd-fdd0-4b1d-b1a3-ac63017510c2&remoteEmbed=true&remoteHost=https%3A%2F%2Fonline-lecture.hufs.ac.kr&embedApiId=video-div&interactivity=none&showtitle=false&showbrand=false&autoplay=true&hideoverlay=false';

//기능이 동작한다면 &start=55를 추가


// 인프런 코드

const videoElement = document.evaluate('//*[@id="player-container"]/div[1]/div/video', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
const youtubeLink = 'https://www.youtube.com/embed/ZgGedwSydCE?autoplay=1'; // autoplay 추가

if (videoElement) {
    const iframeElement = document.createElement('iframe');
    iframeElement.src = youtubeLink;
    iframeElement.width = "100%";
    iframeElement.height = "100%";
    iframeElement.frameborder = "0";
    iframeElement.allow = "accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture";
    iframeElement.allowfullscreen = true;
    videoElement.replaceWith(iframeElement);
} else {
    console.log('비디오 요소를 찾을 수 없습니다.');
}
