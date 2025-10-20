// Redirection automatique après 2s sur la splash
setTimeout(()=>{
    if(window.location.pathname === "/"){
        window.location.href = "/home";
    }
}, 2000);
