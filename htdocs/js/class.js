var g_columns = [];
var dblclick_dict = {};

$(document).ready(function () {

    $("#person-add-row").click(function () {
        var msg = "您真的确定要增加吗？";
        if (confirm(msg) == true) {
            var class_id = this.name.split('-')[1];
            $.post(
                "/person/add",
                "class_name=" + contact_name + "&_xsrf=" + _xsrf_token,
                function (j) {
                    if (j.status == "ok") {
                        var columns = j.result.columns;
                        var person = j.result.person;
                        g_columns = columns;
                        $("#people-list").append(create_row(columns, person));
                        add_editable();
                    }
                    else {
                        show_error(j.msg);
                    }
                }
            );
        }
    });

    $("#check").click(function() {
        document.upform.submit();
        $("#hidenframe")[0].style.display = 'none';
        $("#hidenframe")[0].callback = function(msg) {
            var _html = "";
            console.log(msg);
            for (var i = 0; i < msg["myrows"].length; i++) {
                _html += "<div>";
                _html += "<label>" + msg["myrows"][i] + "对应 :</label>";
                _html += '<select class="fieldsel" name="column-"' + i + '-' + msg["myrows"][i] + '">';
                for (var j = 0; j < msg["sysrows"].length; j++) {
                    _html += "<option value=\"" + msg["sysrows"][j] + "\">";
                    _html += msg["sysrows"][j];
                    _html += "</option>";
                }
                _html += "</select>";
                _html += "</div>";
            }
            _html += '<input type="hidden" name="_xsrf" value="' + _xsrf_token + '">';
            _html += '<input type="hidden" name="filepath" value="' + msg["file"] + '">';
            _html += '<input type="submit" value="submit"/>';
            $("#check-content").html(_html);
        };
    });

    load_people_list();
});

function create_row(columns, person) {
    var row = "<tr>";
    for (var i = 0; i < columns.length; i++) {
        var td = "<td " +
				"data-item='" + columns[i] + "' " +
				"class='edit-" + columns[i] + "' " +
				"id='" + columns[i] + "-" + person._id + "' " +
				">" + person[columns[i]] + "</td>";
        row += td;
    }
    row += '<td>' +
        '<button type="button" class="btn btn-default btn-xs hidden" ' +
        'name="btn-del">删除</button>' +
        '</td>' + "</tr>";

    return row;
}

function update_person(value, settings) {
    var self = $(this);
    var old_value = this.revert;

    var data = {_id: this.id.split("-")[1], what: this.id.split("-")[0],
				value: value, _xsrf: _xsrf_token, class_name: contact_name};

    $.post("/person/update",
           data,
           function (json) {
               console.log(json);
               if (json.status == "ok") {
                   self.text(json.result.new_value);
               }
               else {
                   self.text(old_value);
				   show_error(json.msg);
               }
           });

    return value;
}

function add_editable() {
    var columns = g_columns;

    for (var i = 0; i < columns.length; i++) {
        var name = ".edit-" + columns[i];

        $(name).editable(
            update_person,{
                // width: 100,
                submit: '修改',
				placeholder: "",
				event: "jeditable-edit",
				indicator: "保存中...",
				tooltip: "点击编辑..."
            });
    }

    $("button[name=btn-del]").on("click", function () {
        var msg = "您真的确定要删除吗？";
        if (confirm(msg) == true) {
            var tr = $(this).parent().parent();
            var user_id = tr.children("td.edit-name").attr("id").split("-")[1];
            $.post(
                "/person/delete",
                "_id=" + user_id + "&_xsrf=" + _xsrf_token,
                function (j) {
                    if (j.status == "ok") {
                        tr.remove();
                    }
                    else {
                        show_error(j.msg);
                    }
                });
            return false;
        } else {
            return false;
        }
    });
}

function load_people_list() {
    var i;
    $.ajax({
        url: "/class/people",
        data: "class_name=" + contact_name,
        type: "get",
        cache: false, 		   // fuck ie6
        dataType: "json",
        success: function(json) {
            if (json.status == "ok") {
                var result = json.result;
                var columns = json.result.columns;
                var columns_name_dict = json.result.columns_name_dict;
                var people = json.result.people;
                g_columns = columns;

                // add head
                var thead = "<tr>";
                for (i = 0; i < columns.length; i++) {
                    thead += '<td data-item="' + columns[i] + '" class="danger">' + columns_name_dict[columns[i]] + '</td>';
                }
                thead +='<td class="danger"></td>';
                thead += "</tr>";
                $("#people-list > thead").html(thead);

                var time = 0;
                var interval = 20;
                var _do = (function(people) {
                    return function(){
                        var index = 0;
                        var rows_html = "";
                        while(index < interval && (time * interval + index) < people.length) {
                            var person = people[time * interval + index];
                            rows_html += create_row(columns, person);
                            index ++;
                        }
                        $("#people-list").append(rows_html);
                        time++;
                        add_editable();
                        hook_weibo_link();
                        hook_item_click();
                        if((time * interval ) < people.length){
                            setTimeout(function(){
                                _do();
                            },0);
                        }
                    };
                })(people);
                _do();
            } else {
                show_error(json.msg);
            }
        }
    });
}

var click_delay = 500;
function hook_weibo_link() {
    $(".edit-weibo").addClass("btn-link btn-small").click(
        function (e) {
            var self = this;
            dblclick_dict[self] = setTimeout(function () {
                var weibo = $(self).text();
                if (weibo.indexOf("http://weibo.com/") == 0) {
                    window.open(weibo);
                }
                else if (weibo.length > 2) {
                    // open weibo search
                    var weibo_search = "http://s.weibo.com/user/" + encodeURI(weibo.replace(/^\s+|\s+$/g, ''));
                    window.open(weibo_search);
                }
                dblclick_dict[self] = null;
            }, click_delay);
        });
}


function hook_item_click() {
    var columns = g_columns;
    for (var i = 0; i < columns.length; i++) {
		if (columns[i] == "name") {
			continue;
		}
        var name = ".edit-" + columns[i];
        $(name).dblclick(function (e) {
            if (dblclick_dict[this]) {
                clearTimeout(dblclick_dict[this]);
                dblclick_dict[this] = null;
            }
            if (!e.ctrlKey && !e.shiftKey) {
				var self = $(this);
				$.post("/accounts/checklogin",
					   data="_xsrf=" + _xsrf_token,
					   function (j) {
						   if (j.status == "ok") {
							   self.trigger("jeditable-edit");
						   }
						   else {
							   if (j.why == "no_login") {
								   show_login(j.msg);
							   }
						   }
					   });
            }
        });
    }
}
