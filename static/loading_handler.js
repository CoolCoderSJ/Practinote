window.onload = () => {
    let msg = "Loading..."
    if (window.location.pathname == "/login") {
        msg = "Generating sample test..."
    }
    if (window.location.pathname == "/notion-intermediary" || window.location.pathname == "/docs-intermediary" || window.location.pathname == "/file-intermediary" || window.location.pathname.startsWith("/answers")) {
        msg = "Generating test..."
    }
    if (window.location.pathname.startsWith("/test")) {
        msg = "Checking answers..."
    }

    document.getElementsByTagName('body')[0].innerHTML += `
    <link rel='stylesheet' href='/static/spinkit.min.css' type='text/css'>
    <div id="loading" class="loading">
    <div class="sk-grid">
  <div class="sk-grid-cube"></div>
  <div class="sk-grid-cube"></div>
  <div class="sk-grid-cube"></div>
  <div class="sk-grid-cube"></div>
  <div class="sk-grid-cube"></div>
  <div class="sk-grid-cube"></div>
  <div class="sk-grid-cube"></div>
  <div class="sk-grid-cube"></div>
  <div class="sk-grid-cube"></div>
    </div>
    <h4>${msg}</h4>
    </div><style>
    .loading {
        z-index: 9999;
        background: rgba(0,0,0,0.5);
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        display: none;
        justify-content: center;
        align-items: center;
        flex-direction: column;
    }
    * {
        --sk-color: #fff;
        --sk-size: 100px;
    }
    .loading h4 {
        background: none;
    }
    </style>`;

    let forms = document.getElementsByTagName("form")
    for (let i=0; i<forms.length;i++) {
        let form = forms[i]
        form.addEventListener("submit", () => {
            document.getElementById("loading").style.display = "flex";
        });
    };
}