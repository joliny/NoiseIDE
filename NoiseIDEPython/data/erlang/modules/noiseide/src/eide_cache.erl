-module(eide_cache).

-include_lib("edoc/src/edoc_types.hrl").
 
-define(log(P), io:format("~p~n", [P])).
-define(TERM, "term()").
-define(VAR, "Var"). 
  
-export([ 
    %generate/2,
    generate/3,
    create_cache/2,
    create_cache/4, 
    create_cache_for_erlang_libs/2,
    create_cache_file_fly/2,
    generate_file/4,
    %generate_html_file/3, 
    ignores/0,
    gen_file_cache/1,
    gen_erlang_cache/0, 
    gen_project_cache/0   
]).

-record(function, {  
    name,
    line = 0 :: integer(), 
    params = [],  
    types = [],  
    result,
    exported,
    doc,
    bif = false,    
    comment = []     
}).

-record(content, {
    module_name :: atom(),  
    file,
    last_file_attr,
    beam = false,
    functions = [],  
    specs = [],
    records = [], 
    macros = [],          
    includes = [],
    exports = [] 
}).  

-record(spec, {name, vars = [], types = [], result}).

-record(record, {name, line, fields = [], file}).

-record(field, {name, type}).

-record(macro, {name, value, line, file}).
%erlang_cache:create_cache_for_erlang_libs("D:/temp/erlang_cache", erlang_cache:ignores()).
%erlang_cache:create_cache("d:/temp/erlang_cache", "d:/projects/joe/server/apps", undefined, erlang_cache:ignores()).
%erlang_cache:create_cache("d:/temp/erlang_cache", "d:/projects/gijoe/server/apps", undefined, erlang_cache:ignores()).
%eide_cache:generate_file("D:/temp/erlang_cache", "eide_cache", "d:/Proects/noiseide/noiseidepython/data/erlang/modules/noiseide/src/eide_cache.erl", "", []).
%appmon, aptransform, asn, commontest, compiler, cosEvent, cosEventDomain, cosFileTransfer, cosNotification, cosProperty, cosTime, cosTransactions, couchbeam, crypto, debugger, dialyzer, diameter, edoc, ejson, erldocgen, erlinterface, erts, et, eunit, genleader, gproc, gs, hipe, ibrowse, ic, inets, inviso, jinterface, kernel, megaco, mnesia, mochiweb, oauth, observer, odbc, orber, osmon, otpmibs, parsetools, percept, pman, proper, publickey, reltool, runtimetools, sasl, sha, snmp, ssh, ssl, stdlib, syntaxtools, testserver, toolbar, tools, tv, typer, webtool, wx

%eide_cache:generate_file("D:/temp/erlang_cache", "eide_cache", "d:/Projects/noiseide/noiseidepython/data/erlang/modules/noiseide/src/eide_cache.erl", undefined, []).
%eide_cache:generate_file("D:/temp/erlang_cache", "unit_building", "d:/Projects/GIJoe/server/apps/gamelib/src/units/unit_building.erl", undefined, []).
%ololololo comment
gen_file_cache(File) ->
    case eide_connect:prop(project_dir) of
        undefined -> create_cache(eide_connect:prop(cache_dir) ++ "/other", File);
        Dir ->  
            case lists:prefix(Dir, File) of 
                false -> create_cache(eide_connect:prop(cache_dir) ++ "/other", File);
                _ -> create_cache(eide_connect:prop(cache_dir) ++ "/" ++ eide_connect:prop(project_name), File)
            end
    end. 

gen_erlang_cache() ->
    io:format("Checking cache for erlang libs..."),
    create_cache_for_erlang_libs(eide_connect:prop(cache_dir) ++ "/erlang", ignores()),
    io:format("...Done").

gen_project_cache() ->
    io:format("Checking cache for project..."),
    create_cache(eide_connect:prop(cache_dir) ++ "/" ++ eide_connect:prop(project_name), eide_connect:prop(project_dir), undefined, ignores()),
    io:format("...Done").

ignores() ->
    [appmon, asn, cosEvent, cosEventDomain, 
     cosFileTransfer, cosNotification, cosProperty, 
     cosTime, cosTransactions, parsetools, percept, 
     erldocgen, erlinterface, et, gs, hipe, ic, 
     inviso, jinterface, megaco, observer, orber, osmon, 
     otpmibs, runtimetools, testserver, toolbar, 
     tv, typer, webtool, wx]. 

prepare_ignores(AppsPath, IgnoreApps) ->
    Dir = case AppsPath == code:root_dir() of true -> "/lib/"; _ -> "/" end,
    [ AppsPath ++ Dir ++ atom_to_list(A) ++ "-" || A <- IgnoreApps].

create_cache_for_erlang_libs(CacheDir, IgnoreApps) ->
    create_cache(CacheDir, code:root_dir(), undefined, IgnoreApps).

create_cache(CacheDir, File) ->
    generate_file(CacheDir, module_name(File), File, undefined),
    ok.

create_cache_file_fly(FlyFile, RealFile) ->
    CacheDir =  
        case eide_connect:prop(project_dir) of
            undefined -> eide_connect:prop(cache_dir) ++ "/other";
            Dir -> 
                case lists:prefix(Dir, RealFile) of 
                    false -> eide_connect:prop(cache_dir) ++ "/other";
                    _ -> eide_connect:prop(cache_dir) ++ "/" ++ eide_connect:prop(project_name)
                end
                
        end,
    RealModuleName = module_name(RealFile),    
    ModuleName = module_name(FlyFile),    
    CacheFileName = get_cache_file_name(CacheDir, RealModuleName),
    try 
       Data = generate(ModuleName, FlyFile, undefined), 
       dump_data_to_file(RealModuleName, CacheDir, RealFile, CacheFileName, Data, FlyFile),
       send_answer(CacheDir, CacheFileName, RealFile)
    catch _:_ -> ok
    end,  
    ok.

add_paths(AppsPath) ->
    {ok, Apps} = file:list_dir(AppsPath),
    [code:add_patha(Ai) || A <- Apps,
     begin
         Ai = AppsPath ++ "/"++A++"/ebin",
         filelib:is_dir(Ai)
     end].

create_cache(CacheDir, AppsPath, App, IgnoreApps) ->
    LibDir = 
        case App of 
            undefined -> AppsPath;
            _ -> AppsPath ++ "/" ++ App
        end,
    add_paths(AppsPath),
    Ignores = prepare_ignores(AppsPath, IgnoreApps),
    Files = filelib:fold_files(LibDir, ".*\.(erl|hrl|html)$", true, 
                               fun(File, A) ->
                                   case lists:any(fun(IApp) -> 
                                                      lists:prefix(IApp, File) 
                                                  end, Ignores) of
                                       true -> 
                                           A;
                                       _ -> 
                                           Ext = filename:extension(File),
                                           ModuleName = module_name(File),
                                           case Ext of
                                               ".erl" ->
                                                   case dict:find(ModuleName, A) of
                                                       {ok, {_, D}} ->
                                                           dict:store(ModuleName, {File, D}, A);
                                                       error ->
                                                           dict:store(ModuleName, {File, undefined}, A)
                                                   end;
                                               ".hrl" -> 
                                                   dict:store(ModuleName, {File, undefined}, A);
                                               ".html" ->
                                                   case dict:find(ModuleName, A) of
                                                       {ok, {F, _}} ->
                                                           dict:store(ModuleName, {F, File}, A);
                                                       error ->
                                                           dict:store(ModuleName, {undefined, File}, A)
                                                   end;
                                               _ -> A
                                           end
                                   end 
                               end, dict:new()),
    [generate_file(CacheDir, Name, File, Docs) || {Name, {File, Docs}} <- dict:to_list(Files), File =/= undefined],
    ok.

module_name(File) ->
    Ext = filename:extension(File),
    ModuleName = filename:rootname(filename:basename(File)),
    case Ext of
        ".hrl" -> ModuleName ++ ".hrl";
        _ -> ModuleName
    end.

get_cache_file_name(CacheDir, Name) ->
    CacheDir ++ "/" ++ Name ++ ".cache".

generate_file(CacheDir, ModuleName, FilePath, DocsFilePath) ->
    try
        CacheFileName = get_cache_file_name(CacheDir, ModuleName),
        case filelib:last_modified(FilePath) < filelib:last_modified(CacheFileName) of
            true -> 
                ignore;
            _ -> 
                Data = generate(ModuleName, FilePath, DocsFilePath),
                dump_data_to_file(ModuleName, CacheDir, FilePath, CacheFileName, Data)
        end,
        send_answer(CacheDir, CacheFileName, FilePath)
    %catch _:_ ->  
    catch Error:Reason ->
            %ok
            io:format("File:~pError:~p, ~p~n~p~n", [FilePath, Error, Reason, erlang:get_stacktrace()])
            %file:write_file(CacheFileName ++ ".error", [Error, Reason])
    end,
    ok.

send_answer(CacheDir, CacheFile, File) ->
    case lists:suffix("erlang", CacheDir) of
        false -> 
            Response = mochijson2:encode({struct, [
                {response, gen_file_cache},   
                {path, iolist_to_binary(File)},     
                {cache_path, iolist_to_binary(CacheFile)}]
                }), 
            eide_connect:send(Response);
        _ ->
            ok
    end.

dump_data_to_file(ModuleName, CacheDir, FilePath, CFile, Content) ->
    dump_data_to_file(ModuleName, CacheDir, FilePath, CFile, Content, FilePath).

dump_data_to_file(ModuleName, CacheDir, FilePath, CFile, Content, FlyFileName) ->
    #content{module_name = MN, 
             functions = Funs, 
             records = Recs, macros = Macs, 
             includes = Incs} = Content, 
    %io:format("Data:~p~n", [{FlyFileName, Recs}]),
    JsonStruct = 
        {struct, [ 
                  {name,list_to_binary(ModuleName)},
                  {file, list_to_binary(FilePath)},
                  {funs, funs_to_json(MN, CacheDir, Funs)},
                  {macros, {struct, macros_to_json(Macs, FlyFileName)}},
                  {includes, includes_to_json(Incs)},
                  {records_data, {struct, recs_data_to_json(Recs, FlyFileName)}}
                 ]
        },
    write_json(CFile, JsonStruct).

write_json(File, Json) ->
    StringData = iolist_to_binary(lists:flatten(mochijson2:encode(Json))),
    file:write_file(File, StringData).
 
funs_to_json(ModuleName, CacheDir, Funs) -> 
    lists:reverse([fun_to_json(ModuleName, CacheDir, F) || F <- Funs]).

fun_to_json(ModuleName, CacheDir, Fun) ->
    {Name, Arity} = Fun#function.name,
    DocRef =  
        case Fun#function.doc of
            undefined -> [];
            Text ->
                FileName = ModuleName ++ "_" ++ Name ++ "-" ++ integer_to_list(Arity) ++ ".fun",
                FullPath = CacheDir ++ "/" ++ FileName,
                file:write_file(FullPath, iolist_to_binary(Text)),
                FileName
        end, 
    Data =  
    [
     {name, iolist_to_binary(Name)},
     {arity, Arity},
     {line, Fun#function.line},
     {exported, Fun#function.exported},
     {params, lists:map(fun iolist_to_binary/1, Fun#function.params)},
     {types, lists:map(fun iolist_to_binary/1, Fun#function.types)},
     {result, iolist_to_binary(Fun#function.result)}
    ],
    Data1 = 
        case Fun#function.comment of 
            [] -> Data;
            _ ->Data ++ [{comment, iolist_to_binary(Fun#function.comment)}]
        end,
    Data2 = 
        case DocRef of 
            [] -> Data1;
            _ ->Data1 ++ [{docref, iolist_to_binary(DocRef)}]
        end,
    case ModuleName == "erlang" of
        true -> Data2 ++ [{bif, Fun#function.bif}];
        _ -> Data2
    end.

recs_data_to_json(Recs, File) ->
    [rec_data_to_json(R) || R <- Recs, string:to_lower(R#record.file) == string:to_lower(File)].

rec_data_to_json(Rec) ->
    {Rec#record.name, {struct, [{fields, rec_fields_to_json(Rec#record.fields)}, 
                                {line, Rec#record.line}]}
    }.

macros_to_json(Macs, File) ->
    [macros_data_to_json(M) || M <- Macs, string:to_lower(M#macro.file) == string:to_lower(File)].

macros_data_to_json(Mac) ->
    {Mac#macro.name, {struct, [{value, iolist_to_binary(Mac#macro.value)}, 
                                {line, Mac#macro.line}]}
    }.

rec_fields_to_json(Fields) ->
    [list_to_binary(F) || #field{name = F} <- Fields].
 
includes_to_json(Incs) ->
    [iolist_to_binary(filename:basename(I)) || I <- Incs].

generate(ModuleName, FilePath, DocsFilePath) -> 
    {StartContent, SyntaxTree} = 
        case filename:extension(FilePath) of
            ".erl" ->
                generate_from_source(FilePath);
            ".hrl" -> 
                generate_from_source(FilePath);
            _ -> 
                throw(unknown_type)
        end,
    Comments = erl_comment_scan:file(FilePath),
    {SyntaxTree1, _} = erl_recomment:recomment_tree(SyntaxTree, Comments),
    %io:format("~p~n", [SyntaxTree1]),
    Content = parse_tree(SyntaxTree1, StartContent),
    Content1 = case DocsFilePath of
                   undefined -> Content;
                   _ -> merge_with_docs(Content, DocsFilePath)
               end,
    Incls = sets:to_list(sets:from_list(Content1#content.includes)),
    Content1#content{includes = Incls, file = FilePath, module_name = ModuleName}.

generate_from_source(Path) -> 
    {ok, Source} = epp_dodger:parse_file(Path),
    {#content{file = Path, last_file_attr = Path}, erl_syntax:form_list(Source)}.

parse_tree(Node, Content) ->
    case erl_syntax:type(Node) of
        form_list -> 
            lists:foldl(fun parse_tree/2, Content,
                        erl_syntax:form_list_elements(Node));
        
        attribute ->
            Name = erl_syntax:attribute_name(Node),
            case erl_syntax:type(Name) of
                atom ->
                    parse_atom(Node, erl_syntax:atom_literal(Name), Content);
                _ ->
                    Content
            end;
        
        function ->
            Function = parse_erlang_function(Node, Content, erl_syntax:get_precomments(Node)),
            NameInfo = erl_syntax:function_name(Node),
            Name = erl_syntax:atom_value(NameInfo),
            Arity = erl_syntax:function_arity(Node),
            Exported = 
                case Content#content.exports of
                    all -> true;
                    _ -> lists:member({Name, Arity}, Content#content.exports)
                end,
            Functions = [Function#function{exported = Exported}|Content#content.functions],
            Content#content{functions = Functions};
        
        comment -> Content;
        _ ->
            Content
    end.

parse_atom(Node, "file", Content) when Content#content.file == undefined  -> 
    [Attribute, _] = erl_syntax:attribute_arguments(Node),
    File = erl_syntax:string_value(Attribute),
    Content#content{file = File, last_file_attr = File}; 
parse_atom(Node, "file", Content) -> 
    [Attribute, _] = erl_syntax:attribute_arguments(Node),
    File = erl_syntax:string_value(Attribute),
    Content1 =     
        case lists:suffix("hrl", File) of
            true -> 
                Content#content{includes = Content#content.includes ++ [File]};
            false -> Content
        end,
    Content1#content{last_file_attr = File}; 
parse_atom(Node, "export", Content) -> 
    case Content#content.exports of
        all ->
            Content;
        _ ->
            [ExportAttrs] = erl_syntax:attribute_arguments(Node),
            Exports = lists:map(fun (Export) ->
                                   parse_export(Export)
                                end,
                      erl_syntax:list_elements(ExportAttrs)),
            Content#content{exports = Content#content.exports ++ Exports}
    end;
parse_atom(Node, "module", Content) -> 
    [Attribute|_] = erl_syntax:attribute_arguments(Node),
    ModuleName = erl_syntax:atom_value(Attribute),
    case is_list(ModuleName) of
        true ->
            throw(skip_module);
        _ ->
            Content#content{module_name = ModuleName}
    end;
parse_atom(Node, "compile", Content) -> 
    [Attribute] = erl_syntax:attribute_arguments(Node),
    case erl_syntax:atom_value(Attribute) of
        export_all ->
            Content#content{exports = all};
        _ ->
            Content
    end; 
parse_atom(Node, "include", Content) -> 
    Includes = Content#content.includes ++ [parse_include(Node)],
    Content#content{includes = Includes};
parse_atom(Node, "include_lib", Content) -> 
    Includes = Content#content.includes ++ [parse_include(Node)],
    Content#content{includes = Includes};
parse_atom(Node, "record", Content) -> 
    Record = parse_erlang_record(Node, Content),
    Records = Content#content.records ++ [Record#record{file = Content#content.last_file_attr}],
    Content#content{records = Records};
parse_atom(Node, "define", Content) -> 
    Macro = parse_erlang_macro(Node),
    Macros = Content#content.macros ++ [Macro#macro{file = Content#content.last_file_attr}],
    Content#content{macros = Macros};
parse_atom(Node, "spec", Content) -> 
    Specs = parse_spec(Node),
    case Specs of 
        [] -> 
            Content;
        _ ->
            Content#content{specs = Content#content.specs ++ Specs}
    end; 
parse_atom(_Node, _Atom, Content) -> 
    Content.

parse_export(Export) ->
    {erl_syntax:atom_value(erl_syntax:arity_qualifier_body(Export)),
     erl_syntax:integer_value(erl_syntax:arity_qualifier_argument(Export))}.

parse_include(Node) ->
    [Arg] = erl_syntax:attribute_arguments(Node),
    erl_syntax:string_value(Arg).       

parse_erlang_function(Node, Content, Comments) ->
    %io:format("fun:~p~n", [Node]),
    NameInfo = erl_syntax:function_name(Node),
    Name = erl_syntax:atom_literal(NameInfo),
    Line = erl_syntax:get_pos(NameInfo),
    Arity = erl_syntax:function_arity(Node),
    [Clause|_] = erl_syntax:function_clauses(Node),
    Params = 
        [begin
             Var = node_value(P, erl_syntax:type(P)),
             Var
         end || P <- erl_syntax:clause_patterns(Clause)],
    Spec = case lists:keyfind({Name, Arity}, #spec.name, Content#content.specs) of 
               false -> undefined;
               S -> S#spec{name = element(1, S#spec.name)}
           end,
    
    Params1 = case Spec of
                  undefined -> Params;
                  Spec -> Spec#spec.vars
              end,
    Result = 
        case Spec of
            undefined -> "term()";
            Spec -> Spec#spec.result
        end,
    Types = case Spec of
                undefined -> [];
                _ -> Spec#spec.types
            end,
    Comment =
        case Comments of
            [] -> [];
            _ ->
                C = lists:last(Comments),
                erl_prettypr:format(C)
        end,
    %io:format("~p > ~p~n", [Name, Comments]),
    #function{name = {Name, Arity},
              line = Line,
              params = Params1,
              types = Types,
              result = Result,
              comment = Comment}.

node_value(Node, variable) ->
    erl_syntax:variable_literal(Node);
node_value(_Node, atom) ->
    "Atom";
node_value(_Node, string) ->
    "String";
node_value(_Node, list) ->
    "List";
node_value(_Node, nil) ->
    "List";
node_value(_Node, tuple) ->
    "Tuple";
node_value(Node, record_expr) ->
    try 
        Record = atom_to_list(element(3, Node)),
        string:to_upper(string:substr(Record, 1, 1)) ++ string:substr(Record, 2)
    catch _:_ -> "Record"
    end;
node_value(Node, match_expr) ->
    try 
        erl_syntax:variable_literal(erl_syntax:match_expr_body(Node))
    catch _:_ -> ?VAR
    end;
node_value(_Node, _) ->
    ?VAR.

parse_spec(Node) ->
    try
        [parse_spec_internal(Node, 1)]
    catch 
        %Error:Reason -> io:format("Error:~p~n. Reason:~p~n parsing spec for:~p~n", [Error, Reason, erlang:get_stacktrace()]),
        _Error:_Reason -> 
            ok,
            []
    end.

parse_spec_internal(Node, Clause) ->
    Spec = edoc_specs:spec(Node, Clause),
    {_, _, _, _, TSpec} = Spec,
    %io:format("Spec:~p~n", [TSpec]),
    #t_spec{name = Name, type = Type, defs = Defs} = TSpec,
    #t_name{name = FunName} = Name,
    #t_fun{args = Args, range = Range} = Type, 
    {Vars, Types} = get_var_types(Args, Defs),
    Result = parse_t_type_res(Range, Defs),  
    %io:format("V, T, R:~p~n", [{Vars, Types, Result}]),
    #spec{name = {atom_to_list(FunName), length(Args)}, vars = Vars, result = Result, types = Types}.

get_var_types(Args, Defs) ->
    {Vars, Types} = 
        lists:foldl(fun(A, {Vars, Types}) ->
                        Var = parse_t_type_var(A),
                        case Var of
                            {T, V} -> {Vars ++ [V], Types ++ [T]};
                            _ -> 
                                #t_var{name = Name} = A,
                                Type = 
                                    case lists:keyfind(#t_var{name = Name}, #t_def.name, Defs) of
                                        #t_def{type = T} -> 
                                            parse_t_type(T, Defs);
                                        _ -> ?TERM 
                                    end, 
                                {Vars ++ [Var], Types ++ [Type]}
                        end
                    end, 
                    {[], []}, 
                    Args),  
    {Vars, Types}.  

parse_t_type_var(#t_nil{}) -> 
    {"nil()", "[]"};
parse_t_type_var(#t_atom{val = Val}) ->
    {"atom()", atom_to_list(Val)};
parse_t_type_var(#t_integer{val = Val}) -> 
    {"integer()", integer_to_list(Val)};
parse_t_type_var(#t_float{val = Val}) ->
    {"float()", float_to_list(Val)};  
parse_t_type_var(#t_name{name = Name}) ->
    case Name of
        Name when is_atom(Name) -> {?TERM, atom_to_list(Name)};
        _ -> {?TERM, ?VAR}
    end;
parse_t_type_var(#t_var{name = Names}) ->
    atom_to_list(case Names of
                      Names when is_list(Names) -> lists:first(Names);
                      _ -> Names
                 end);
parse_t_type_var(#t_type{name = Name, a = Args}) when is_atom(Name) ->
    %io:format("1Name:~p, Args:~p~n", [Name, Args]),
    {atom_to_list(Name) ++ "()", args_to_name(Args)}; 
parse_t_type_var(#t_type{name = Name, a = Args}) when is_record(Name, t_name) ->
    %io:format("2Name:~p, Args:~p~n", [Name, Args]),
    {_, Type} = parse_t_type_var(Name),
    {Type ++ "()", args_to_name(Args)}; 
parse_t_type_var(_) -> 
    {?TERM, ?VAR}.

parse_t_type_res(#t_nil{}, _) ->
    "[]";
parse_t_type_res(#t_atom{val = Val}, _) ->
    atom_to_list(Val);
parse_t_type_res(#t_integer{val = Val}, _) ->
    integer_to_list(Val);
parse_t_type_res(#t_float{val = Val}, _) ->
    float_to_list(Val);
parse_t_type_res(#t_union{types = Types}, Defs) ->
    "(" ++ string_join([parse_t_type_res(T, Defs) || T <- Types], " | ") ++ ")";
parse_t_type_res(#t_tuple{types = Types}, Defs) ->
    "{" ++ string_join([parse_t_type_res(T, Defs) || T <- Types], ", ") ++ "}";
parse_t_type_res(#t_list{type = Type}, Defs) ->
    "[" ++ parse_t_type_res(Type, Defs) ++ "]";
parse_t_type_res(#t_type{name = Name, args = Types}, Defs) ->
    parse_t_type_res(Name, Defs) ++ "(" ++ string_join([parse_t_type_res(T, Defs) || T <- Types], ", ") ++ ")";
parse_t_type_res(#t_name{name = Name}, _) ->
    case Name of
        Name when is_atom(Name) -> atom_to_list(Name);
        _ -> ?TERM
    end; 
parse_t_type_res(#t_var{name = Names}, Defs) ->
    Name = case Names of
               Names when is_list(Names) -> lists:first(Names);
               _ -> Names
           end,
    Type = 
        case lists:keyfind(#t_var{name = Name}, #t_def.name, Defs) of
            #t_def{type = T} -> 
                parse_t_type(T, Defs);
            _ -> ?TERM  
        end,
    atom_to_list(Name) ++ " :: " ++ Type;
parse_t_type_res(_, _) -> 
    ?TERM.
parse_t_type(T, Deps) -> 
    parse_t_type(T, Deps, 3).

parse_t_type(_, _, 0) -> ?TERM;
parse_t_type(#t_type{name = Name}, _, _) when is_atom(Name) ->
    atom_to_list(Name) ++ "()"; 
parse_t_type(#t_type{name = Name}, Defs, Depth) when is_record(Name, t_name) ->
    parse_t_type(Name, Defs, Depth - 1); 
parse_t_type(#t_name{module = Module, name = Name}, _, _) ->
    Result = case Module of [] -> ""; _ -> atom_to_list(Module) ++ ":" end,
    Result ++ atom_to_list(Name) ++ "()";  
parse_t_type(#t_atom{val = Val}, _, _)->
    atom_to_list(Val); 
parse_t_type(#t_record{name = #t_atom{val = Name}}, _, _)->
    "#" ++ atom_to_list(Name) ++ "{}"; 
parse_t_type(#t_union{types = Types}, Defs, Depth) -> 
    string_join([parse_t_type(T, Defs, Depth - 1) || T <- Types], " | ");
parse_t_type(#t_tuple{types = Types}, Defs, Depth) ->
    "{" ++ string_join([parse_t_type(T, Defs, Depth - 1) || T <- Types], ", ") ++ "}";
parse_t_type(#t_list{type = Type}, Defs, Depth) ->
    "[" ++ parse_t_type(Type, Defs, Depth - 1) ++ "]";
parse_t_type(#t_var{name = Names}, Defs, Depth) ->
    Name = case Names of
               Names when is_list(Names) -> lists:first(Names);
               _ -> Names
           end,
    case lists:keyfind(#t_var{name = Name}, #t_def.name, Defs) of
        #t_def{type = T} -> 
            parse_t_type(T, Defs, Depth - 1);
        _ -> ?TERM 
    end;
parse_t_type(_, _, _) -> ?TERM.

string_join(Items, Sep) ->
    lists:flatten(lists:reverse(string_join1(Items, Sep, []))).
string_join1([], _Sep, Acc) ->  
    Acc;
string_join1([Head | []], _Sep, Acc) ->
    [Head | Acc];
string_join1([Head | Tail], Sep, Acc) ->
    string_join1(Tail, Sep, [Sep, Head | Acc]).

args_to_name([]) -> ?VAR;
args_to_name(Args) -> atom_to_list(hd(Args)).

parse_erlang_record(Node, Content) ->
    Record = lists:foldl(
                         fun(Arg, InnerRecord) ->
                             case erl_syntax:type(Arg) of
                                 atom ->
                                     InnerRecord#record{name = erl_syntax:atom_name(Arg)};
                                 tuple -> 
                                     parse_erlang_record_fields(erl_syntax:tuple_elements(Arg), InnerRecord);
                                 macro ->
                                     MacroName = erl_syntax:variable_literal(erl_syntax:macro_name(Arg)), 
                                     Result = lists:filter(fun(Macro) -> 
                                                               Macro#macro.name == MacroName
                                                           end,
                                                           Content#content.macros),
                                     Name = 
                                         case Result of 
                                             [] -> 
                                                 "name_cannot_be_resolved"; 
                                             [Macro] -> 
                                                 Macro#macro.value 
                                         end,
                                     InnerRecord#record{name = Name}
                             end
                         end,
                         #record{},
                         erl_syntax:attribute_arguments(Node)),
    
    Record#record{line = erl_syntax:get_pos(Node)}.

parse_erlang_record_fields(Fields, Record) -> 
    lists:foldl(
                fun(Field, InnerRecord) ->  
                    FieldName = erl_syntax:record_field_name(Field),
                    Name = case erl_syntax:type(FieldName) of
                               atom ->
                                   erl_syntax:atom_name(FieldName);
                               _ -> throw(unknown_record_field_name)
                           end,
                    InnerRecord#record{fields = InnerRecord#record.fields ++ [#field{name = Name}]}
                end,
                Record, 
                Fields).

parse_erlang_macro(Node) -> 
    [Define | Definition] = erl_syntax:attribute_arguments(Node),
    [Def| _] = Definition,
    Macro = erl_prettypr:format(Define),
    Value = erl_prettypr:format(Def),
    #macro{name = Macro, value = Value, line = erl_syntax:get_pos(Node)}.

merge_with_docs(Content, DocsFilePath) ->
    Functions = get_functions_data_from_html(DocsFilePath),
    lists:foldl(fun add_data_from_html_fun/2, Content, Functions).

get_functions_data_from_html(File) ->
    {ok, Data} = file:read_file(File),
    Result = re:run(Data, <<"(<p><a name=.*?</div>\\s*(?=<p><a name=|<div class=\"footer\">))">>,
                    [multiline, dotall, global, {capture, [1], list}]),
    case Result of
        {match, Captured} ->
            FunsData = 
                [begin
                     FunsResult = re:run(Text, <<"<a name=\"([A-Za-z_:]*?)-([0-9]?)\">(?:</a>)?<span.*?>(.*?)\\((.*?)\\)\\s*-&gt;\\s*(.*?)</span>">>,
                                         [multiline, dotall, global, {capture, [1, 2, 3, 4, 5], list}]),
                     case FunsResult of
                         {match, Funs} ->
                             [{F, Text} || F <- Funs];
                         _ -> []
                     end
                 end || [Text] <- Captured],
            lists:append(FunsData);
        _ -> []
    end.

add_data_from_html_fun({[FunName, Arity, SpecName, Params, _Result], Text}, Content) ->
    Arity1 = list_to_integer(Arity),
    SimpleParams = re:run(Params, <<"[A-Za-z_0-9,\s]*">>),
    case lists:keyfind({FunName, Arity1}, #function.name, Content#content.functions) of
        Fun when is_record(Fun, function) -> 
            NewFun = 
                case SimpleParams of
                    true -> Fun#function{params = [Params], result = ?TERM, doc = Text};
                    _ -> Fun#function{doc = Text}
                end,
            Content#content{functions = lists:keyreplace({FunName, Arity1}, #function.name, Content#content.functions, NewFun)};
        _ -> 
            IsBif = case SpecName of "erlang:" ++ _ -> false; _ -> true end,
            NewFun = #function{name = {FunName, Arity1}, params = [Params], result = ?TERM, doc = Text, bif = IsBif, exported = true},
            Content#content{functions = [NewFun|Content#content.functions]}
    end.

