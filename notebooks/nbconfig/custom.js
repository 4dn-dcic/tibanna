$("<style type='text/css'> .cell.code_cell.collapse { max-height:30px; overflow:hidden;} </style>").appendTo("head");
$('.prompt.input_prompt').on('click', function(event) {
    console.log("CLICKED", arguments)   
    var c = $(event.target.closest('.cell.code_cell'))
    if(c.hasClass('collapse')) {
        c.removeClass('collapse');
    } else {
        c.addClass('collapse');
    }
});