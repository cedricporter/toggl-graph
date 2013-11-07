// Author: Hua Liang[Stupid ET]


var bPopup_config = {
    speed: 0,
    opacity: 0.2
};

// auto show loading when ajax running
$(document).ajaxStart(function(){
    show_loading();
}).ajaxStop(function(){
    hide_loading();
});

$(document).ready(function () {

    $("#login-form").ajaxForm(function (json) {
        if (json.status == "ok") {
            setTimeout(hide_login, 0);
        }
        else {
            set_login_msg(json.msg);
        }
    });

    $("#feedback-form").ajaxForm(function (json) {
        if (json.status == "ok") {
            hide_feedback();
        } else {
            $("#feedback-form-tip").text(json.msg);
        }
    });

});

function show_msgbox(title, msg) {
    $("#pop-msg-box [name=title]").html(title);
    $("#pop-msg-box p[name=content]").html(msg);

    $("#pop-msg-box").bPopup(bPopup_config);
}

function set_login_msg(msg) {
    $("#login-pop-box div h2").text(msg);
}

function show_login(msg) {
    $("#login-pop-box").bPopup(bPopup_config);

    set_login_msg(msg);
}

function hide_login() {
    $("#login-pop-box").bPopup(bPopup_config).close();
}

function hide_feedback() {
    $("#feedback").modal("hide");
    $("#feedback [name=email]").val("");
    $("#feedback [name=content]").val("");
}

function show_error(msg) {
    show_msgbox("出错啦！", msg);
}

function hide_loading() {
    $("#spinnerContainer").bPopup().close();
}

function show_loading() {
    $("#spinnerContainer").bPopup(bPopup_config);
    $("#spinnerContainer").spin();
}
