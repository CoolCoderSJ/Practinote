window.onload = () => {
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
    }
    * {
        --sk-color: #fff;
        --sk-size: 100px;
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