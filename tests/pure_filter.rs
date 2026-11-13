use imageinfo::pure_filter::{
    BatchStatus, CompileError, CompiledFilter, Coverage, DeclarationError, Evaluation, ExactNumber,
    ExpressionError, IssueKind, ObservationError, Observations, Occurrence, Registry, Scalar,
    ScalarType, SelectorObservation, Truth, UnknownPolicy, compile,
};
use serde::Deserialize;
use serde_json::{Value, json, value::RawValue};

fn registry() -> Registry {
    Registry::new(
        "authored-v1",
        ["EXIF:ISO", "t", "f", "u", "v", "s", "b", "n", "d"],
        ["ISO"],
        [("http://ns.adobe.com/exif/1.0/", "ISOSpeedRatings")],
    )
    .unwrap()
}

fn request(expression: &str) -> Value {
    json!({
        "version": "pure-data-v1", "registryRevision": "authored-v1",
        "expression": expression, "aliases": [], "parameters": [], "definitions": []
    })
}

fn compile_value(request: &Value, registry: &Registry) -> Result<CompiledFilter, CompileError> {
    compile(&serde_json::to_vec(request).unwrap(), registry)
}

fn filter(expression: &str, registry: &Registry) -> CompiledFilter {
    compile_value(&request(expression), registry).unwrap()
}

fn check_expression_error(expression: &str, expected: ExpressionError, registry: &Registry) {
    assert!(matches!(
        compile_value(&request(expression), registry),
        Err(CompileError::Expression { kind, .. }) if kind == expected
    ));
}

fn occurrence(raw: Option<Scalar>, normalized: Option<Scalar>) -> Occurrence {
    Occurrence { raw, normalized }
}

fn observation(coverage: Coverage, occurrences: Vec<Occurrence>) -> SelectorObservation {
    SelectorObservation {
        coverage,
        occurrences,
    }
}

fn truth_observations(registry: &Registry) -> Observations {
    let mut observed = Observations::new(registry);
    observed
        .insert(
            "t",
            observation(Coverage::Complete, vec![occurrence(None, None)]),
        )
        .unwrap();
    observed
        .insert("f", observation(Coverage::Complete, vec![]))
        .unwrap();
    observed
}

#[test]
fn frozen_request_vectors_and_strict_json() {
    #[derive(Deserialize)]
    struct Vectors<'a> {
        #[serde(borrow)]
        cases: Vec<Case<'a>>,
        #[serde(borrow, rename = "rawCases")]
        raw_cases: Vec<RawCase<'a>>,
    }
    #[derive(Deserialize)]
    struct Case<'a> {
        id: &'a str,
        expected: &'a str,
        #[serde(borrow)]
        request: &'a RawValue,
    }
    #[derive(Deserialize)]
    struct RawCase<'a> {
        id: &'a str,
        expected: &'a str,
        input: String,
    }
    let registry = registry();
    let data: Vectors<'_> = serde_json::from_str(include_str!(
        "../docs/legacy-compatibility/pure-data/vectors.v1.json"
    ))
    .unwrap();
    for case in data.cases {
        let result = compile(case.request.get().as_bytes(), &registry);
        // These envelope-only vectors have accepted declaration shapes, but
        // their shared expression refers to a binding that they omit.
        if matches!(case.id, "empty-declarations" | "count-at-limit") {
            assert!(
                matches!(
                    result,
                    Err(CompileError::Expression {
                        kind: ExpressionError::UnknownAlias,
                        ..
                    })
                ),
                "{}: {result:?}",
                case.id
            );
            continue;
        }
        assert_eq!(
            result.is_ok(),
            case.expected == "accept",
            "{}: {result:?}",
            case.id,
        );
    }
    for case in data.raw_cases {
        assert_eq!(
            compile(case.input.as_bytes(), &registry).is_ok(),
            case.expected == "accept",
            "{}",
            case.id,
        );
    }

    let mut request = request(r#"exists("t")"#);
    let envelope = |replacement: &str| {
        serde_json::to_string(&request)
            .unwrap()
            .replace("\"aliases\":[]", replacement)
    };
    for replacement in [
        r#""aliases":[],"aliase\u0073":[]"#,
        r#""aliases":[{"name":"ok","nam\u0065":"also","selector":"t"}]"#,
        r#""aliases":[{"name":"ok","selector":"t","extra":true}]"#,
        r#""aliases":[["ok","t"]]"#,
        r#""aliases":[{"name":"ok","selector":"\uD800"}]"#,
        r#""aliases":[{"name":"ok","selector":"\uDC00"}]"#,
    ] {
        assert!(
            compile(envelope(replacement).as_bytes(), &registry).is_err(),
            "{replacement}"
        );
    }
    request["parameters"] = json!([{"name":"p","type":"string","value":"MARK"}]);
    let base = serde_json::to_string(&request).unwrap();
    for invalid in [r#""\uD800""#, r#""\uDC00""#, r#"{"x":1,"x":2}"#, "[]"] {
        assert!(compile(base.replace(r#""MARK""#, invalid).as_bytes(), &registry).is_err());
    }
    assert_eq!(compile(b"\xff", &registry).unwrap_err(), CompileError::Utf8);
    assert_eq!(
        compile(b"\xef\xbb\xbf{}", &registry).unwrap_err(),
        CompileError::Bom
    );
    assert!(
        compile(
            br#"["pure-data-v1","authored-v1","exists(\"t\")",[],[],[]]"#,
            &registry
        )
        .is_err()
    );
    assert!(compile(format!("{base} {{}}").as_bytes(), &registry).is_err());
    request["registryRevision"] = json!("other-v1");
    assert_eq!(
        compile_value(&request, &registry).unwrap_err(),
        CompileError::RegistryMismatch
    );
}

#[test]
fn strong_kleene_truth_tables_and_ordered_diagnostics() {
    use Truth::{False, True, Unknown};
    let registry = registry();
    let observations = truth_observations(&registry);
    let names = ["t", "f", "u"];
    let conjunction = [
        [True, False, Unknown],
        [False, False, False],
        [Unknown, False, Unknown],
    ];
    let disjunction = [
        [True, True, True],
        [True, False, Unknown],
        [True, Unknown, Unknown],
    ];
    for (index, lhs) in names.into_iter().enumerate() {
        assert_eq!(
            filter(&format!(r#"not exists("{lhs}")"#), &registry)
                .evaluate(&observations)
                .truth,
            [False, True, Unknown][index]
        );
        for (other, rhs) in names.into_iter().enumerate() {
            for (operator, table, stop) in [("and", conjunction, 1), ("or", disjunction, 0)] {
                let source = format!(r#"exists("{lhs}") {operator} exists("{rhs}")"#);
                let outcome = filter(&source, &registry).evaluate(&observations);
                assert_eq!(outcome.truth, table[index][other]);
                let mut offsets = Vec::new();
                if index == 2 {
                    offsets.push(0);
                }
                if index != stop && other == 2 {
                    offsets.push(source.rfind("exists").unwrap());
                }
                assert_eq!(outcome.issues.len(), offsets.len());
                for (issue, offset) in outcome.issues.iter().zip(offsets) {
                    assert_eq!(issue.kind, IssueKind::IncompleteCoverage);
                    assert_eq!(issue.expression_offset, Some(offset));
                    assert_eq!(issue.selector.as_deref(), Some("u"));
                }
            }
        }
    }

    for (expression, truth) in [
        (r#"exists("t") or exists("f") and exists("f")"#, True),
        (r#"(exists("t") or exists("f")) and exists("f")"#, False),
        (r#"not exists("t") and exists("f")"#, False),
        (r#"not(exists("t")and exists("f"))"#, True),
        (r#"notexists("t") ornotexists("f")"#, True),
        (r#"exists("t")andnotexists("f")"#, True),
        (r#"exists("f")and exists("u")or exists("t")"#, True),
        ("exists\t(\r\"t\"\n)", True),
    ] {
        assert_eq!(
            filter(expression, &registry).evaluate(&observations),
            Evaluation {
                truth,
                issues: vec![]
            }
        );
    }
    check_expression_error(
        r#"exists("t") or exists("missing")"#,
        ExpressionError::UnknownSelector,
        &registry,
    );
    check_expression_error(
        r#"exists("t") or exists(alias("missing"))"#,
        ExpressionError::UnknownAlias,
        &registry,
    );
    check_expression_error(
        r#"exists("f") and value("t","raw")==param("missing")"#,
        ExpressionError::UnknownParameter,
        &registry,
    );
    check_expression_error(
        r#"exists("t") or value("t","raw") == 1e309"#,
        ExpressionError::Number,
        &registry,
    );
    for expression in [
        r#"exists("t") false"#,
        r#"exists("t") || exists("f")"#,
        r#"exists("t") or (exists("f")"#,
        r#"exists("t") or Value("f","raw")==null"#,
        r#"value("t","\u0072aw")==null"#,
        r#"value("t","raw")=null"#,
        "exists\u{000b}(\"t\")",
        "exists\u{a0}(\"t\")",
    ] {
        assert!(
            compile_value(&request(expression), &registry).is_err(),
            "{expression}"
        );
    }
}

#[test]
fn scalar_views_exact_comparison_and_coverage() {
    let registry = registry();
    let mut inputs = truth_observations(&registry);
    for (selector, coverage, occurrences) in [
        (
            "v",
            Coverage::Complete,
            vec![occurrence(
                Some(Scalar::Number(ExactNumber::from_rational(3, 10).unwrap())),
                Some(Scalar::Number(ExactNumber::from_rational(-1, 3).unwrap())),
            )],
        ),
        (
            "s",
            Coverage::Complete,
            vec![occurrence(Some(Scalar::String("é𝄞\n".into())), None)],
        ),
        (
            "n",
            Coverage::Complete,
            vec![occurrence(Some(Scalar::Null), None)],
        ),
        (
            "b",
            Coverage::Complete,
            vec![occurrence(Some(Scalar::Boolean(true)), None)],
        ),
        (
            "d",
            Coverage::Complete,
            vec![occurrence(None, None), occurrence(None, None)],
        ),
        (
            "u",
            Coverage::Incomplete,
            vec![occurrence(Some(Scalar::Null), None)],
        ),
    ] {
        inputs
            .insert(selector, observation(coverage, occurrences))
            .unwrap();
    }
    for expression in [
        r#"value("v","raw")==3.00e-1"#,
        r#"value("v","raw")!=0.30000000000000000000000000000000000000000000000000001"#,
        r#"value("v","normalized")<-0.3333333333333333333333333333333333333333333333333333"#,
        r#"value("v","normalized")>-0.3333333333333333333333333333333333333333333333333334"#,
        r#"value("v","raw")<=30e-2 and value("v","raw")>=30000e-5"#,
        r#"value("s","raw")=="\u00e9\uD834\uDD1E\n""#,
        r#"value("s","raw")!="e\u0301\uD834\uDD1E\n""#,
        r#"value("s","raw")>"e""#,
        r#"value("n","raw")==null and exists("n")"#,
        r#"value("b","raw")==true and value("b","raw")!=false"#,
        r#"value("b","raw")==trueorvalue("b","raw")==false"#,
        r#"exists("u") and not absent("u") and exists("d") and absent("f")"#,
    ] {
        assert_eq!(
            filter(expression, &registry).evaluate(&inputs),
            Evaluation {
                truth: Truth::True,
                issues: vec![]
            },
            "{expression}"
        );
    }
    for (expression, kind) in [
        (r#"value("v","raw")!="0.3""#, IssueKind::TypeMismatch),
        (r#"value("n","raw")<null"#, IssueKind::UnsupportedOrdering),
        (r#"value("b","raw")>=false"#, IssueKind::UnsupportedOrdering),
        (r#"value("d","raw")==null"#, IssueKind::AmbiguousOccurrence),
        (
            r#"value("s","normalized")=="é""#,
            IssueKind::UnavailableView,
        ),
        (r#"value("u","raw")==null"#, IssueKind::IncompleteCoverage),
        (r#"value("f","raw")==null"#, IssueKind::MissingOccurrence),
    ] {
        let evaluation = filter(expression, &registry).evaluate(&inputs);
        assert_eq!(evaluation.truth, Truth::Unknown, "{expression}");
        assert_eq!(evaluation.issues.len(), 1);
        assert_eq!(evaluation.issues[0].kind, kind);
    }
    assert_eq!(
        inputs.insert("unknown", observation(Coverage::Complete, vec![])),
        Err(ObservationError::UnknownSelector)
    );
    assert_eq!(
        inputs.insert("v", observation(Coverage::Complete, vec![])),
        Err(ObservationError::DuplicateSelector)
    );
    assert_eq!(
        filter(r#"exists("v")"#, &registry).evaluate(&inputs).truth,
        Truth::True
    );
    assert!(ExactNumber::from_rational(0, 0).is_none());
    assert_eq!(
        ExactNumber::from_json_number("-0e-308"),
        ExactNumber::from_rational(0, 1)
    );
    assert!(
        ExactNumber::from_rational(i128::MIN, u128::MAX).unwrap()
            < ExactNumber::from_json_number("-0.5").unwrap()
    );
    assert!(
        ExactNumber::from_json_number("1e308").unwrap()
            > ExactNumber::from_rational(i128::MAX, 1).unwrap()
    );
    assert!(
        ExactNumber::from_json_number("1e-308").unwrap()
            < ExactNumber::from_rational(1, u128::MAX).unwrap()
    );
}

#[test]
fn request_expression_token_nesting_predicate_and_visit_limits() {
    let registry = registry();
    let observed = truth_observations(&registry);
    let expression = r#"exists("t")"#;
    let base = serde_json::to_string(&request(expression)).unwrap();
    let mut bytes = base.into_bytes();
    bytes.resize(65_536, b' ');
    assert!(compile(&bytes, &registry).is_ok());
    bytes.push(b' ');
    assert_eq!(
        compile(&bytes, &registry).unwrap_err(),
        CompileError::RequestBytes
    );

    let exact = format!(r#"value("t","raw")=="{}""#, "é".repeat(512));
    let mut padded = format!("{exact}{}", " ".repeat(4096 - exact.len()));
    assert!(compile_value(&request(&padded), &registry).is_ok());
    padded.push(' ');
    check_expression_error(&padded, ExpressionError::Bytes, &registry);

    let tokens = |extra: usize| {
        // 128 four-token predicates, 127 binary operators, and 385/386 `not` tokens.
        let mut expression = format!("{}{expression}", "not ".repeat(4 + extra));
        for _ in 0..127 {
            expression.push_str(&format!(
                " and not not not {expression_unit}",
                expression_unit = r#"exists("t")"#
            ));
        }
        expression
    };
    assert!(compile_value(&request(&tokens(0)), &registry).is_ok());
    check_expression_error(&tokens(1), ExpressionError::Tokens, &registry);

    for depth in [32, 33] {
        let group = format!("{}{expression}{}", "(".repeat(depth), ")".repeat(depth));
        let unary = format!("{}{expression}", "not ".repeat(depth));
        if depth == 32 {
            assert!(compile_value(&request(&group), &registry).is_ok());
            assert!(compile_value(&request(&unary), &registry).is_ok());
        } else {
            check_expression_error(&group, ExpressionError::Nesting, &registry);
            check_expression_error(&unary, ExpressionError::Nesting, &registry);
        }
    }
    let chain = |count| vec![expression; count].join(" and ");
    assert_eq!(
        filter(&chain(128), &registry).evaluate(&observed).truth,
        Truth::True
    );
    check_expression_error(&chain(129), ExpressionError::Predicates, &registry);

    let chain_with_visits = |extra: usize| {
        let mut operands = vec![format!("{}{}", "not ".repeat(4 + extra), expression)];
        operands.extend((0..3).map(|_| format!("not not not not {expression}")));
        operands.extend((0..113).map(|_| format!("not {expression}")));
        operands.extend((0..11).map(|_| expression.to_owned()));
        operands.join(" or ")
    };
    let absent = Observations::new(&registry);
    let at_limit = filter(&chain_with_visits(0), &registry).evaluate(&absent);
    assert_eq!(at_limit.issues.len(), 128);
    assert!(
        at_limit
            .issues
            .iter()
            .all(|issue| issue.kind == IssueKind::IncompleteCoverage)
    );
    let over = filter(&chain_with_visits(1), &registry).evaluate(&absent);
    assert_eq!(over.truth, Truth::Unknown);
    assert_eq!(over.issues.last().unwrap().kind, IssueKind::BudgetExhausted);
    assert!(over.issues.last().unwrap().expression_offset.is_some());
    // Even a later determining true must not recover an exhausted evaluation.
    let mut last_true = Observations::new(&registry);
    last_true
        .insert(
            "f",
            observation(Coverage::Incomplete, vec![occurrence(None, None)]),
        )
        .unwrap();
    let source = chain_with_visits(1);
    let last = source.rfind("\"t\"").unwrap();
    let source = format!("{}\"f\"{}", &source[..last], &source[last + 3..]);
    assert_eq!(
        filter(&source, &registry).evaluate(&last_true).truth,
        Truth::Unknown
    );
}

#[test]
fn strict_numeric_spellings_in_both_request_locations() {
    let registry = registry();
    let accepted = [
        "1".repeat(128),
        "1e+308".into(),
        "1e-308".into(),
        "1e0000000000308".into(),
    ];
    let refused = [
        "1".repeat(129),
        "1e309".into(),
        "1e-309".into(),
        "1e+".into(),
        "01".into(),
        "-01".into(),
        "1.".into(),
        "+1".into(),
        ".1".into(),
    ];
    let mut envelope = request(r#"value("t","raw") == param("p")"#);
    envelope["parameters"] = json!([{"name":"p","type":"number","value":"NUMBER_MARKER"}]);
    let template = serde_json::to_string(&envelope).unwrap();
    for (numeric, accepted) in accepted
        .iter()
        .map(|value| (value, true))
        .chain(refused.iter().map(|value| (value, false)))
    {
        assert_eq!(
            ExactNumber::from_json_number(numeric).is_some(),
            accepted,
            "{numeric}"
        );
        assert_eq!(
            compile_value(
                &request(&format!(r#"value("t","raw")=={numeric}"#)),
                &registry
            )
            .is_ok(),
            accepted,
            "{numeric}"
        );
        let wire = template.replace(r#""NUMBER_MARKER""#, numeric);
        assert_eq!(
            compile(wire.as_bytes(), &registry).is_ok(),
            accepted,
            "{numeric}"
        );
    }
    envelope["parameters"][0]["type"] = json!("integer");
    let template = serde_json::to_string(&envelope).unwrap();
    for (numeric, accepted) in [
        ("100e-2", true),
        ("100e-3", false),
        ("-0.00e-308", true),
        ("1e308", true),
        ("true", false),
    ] {
        let wire = template.replace(r#""NUMBER_MARKER""#, numeric);
        assert_eq!(
            compile(wire.as_bytes(), &registry).is_ok(),
            accepted,
            "{numeric}"
        );
    }
}

#[test]
fn declaration_limits_and_literal_authority() {
    let registry = registry();
    let mut envelope = request(r#"exists(alias("a0")) and value("t","raw")==param("p0")"#);
    for index in 0..64 {
        envelope["aliases"]
            .as_array_mut()
            .unwrap()
            .push(json!({"name":format!("a{index}"),"selector":"t"}));
        envelope["parameters"]
            .as_array_mut()
            .unwrap()
            .push(json!({"name":format!("p{index}"),"type":"string","value":""}));
        envelope["definitions"].as_array_mut().unwrap().push(json!({"name":format!("d{index}"),"namespace":"file:///opaque%20name","localName":format!("D{index}"),"type":"integer","provenance":"https://example.invalid/opaque","revision":"v1"}));
    }
    let compiled = compile_value(&envelope, &registry).unwrap();
    assert_eq!(compiled.definitions().len(), 64);
    assert_eq!(compiled.definitions()[63].name, "d63");
    assert_eq!(compiled.definitions()[0].scalar_type, ScalarType::Integer);
    for group in ["aliases", "parameters", "definitions"] {
        let mut excessive = envelope.clone();
        excessive[group].as_array_mut().unwrap().push(Value::Null);
        assert_eq!(
            compile_value(&excessive, &registry).unwrap_err(),
            CompileError::DeclarationCount { group }
        );
    }

    let mut bounded = request(r#"exists("t")"#);
    bounded["aliases"] = json!([{"name":"a".repeat(64),"selector":"t"}]);
    bounded["parameters"] =
        json!([{"name":"p".repeat(64),"type":"string","value":"é".repeat(512)}]);
    bounded["definitions"] = json!([{"name":"d".repeat(64),"namespace":format!("urn:{}", "a".repeat(1020)),"localName":"L".repeat(64),"type":"null","provenance":"é".repeat(512),"revision":"r".repeat(64)}]);
    assert!(compile_value(&bounded, &registry).is_ok());
    for (group, field, extra) in [
        ("aliases", "name", "a"),
        ("parameters", "name", "a"),
        ("parameters", "value", "x"),
        ("definitions", "name", "a"),
        ("definitions", "namespace", "a"),
        ("definitions", "localName", "a"),
        ("definitions", "provenance", "x"),
        ("definitions", "revision", "a"),
    ] {
        let mut over = bounded.clone();
        over[group][0][field] = json!(format!(
            "{}{extra}",
            bounded[group][0][field].as_str().unwrap()
        ));
        assert!(compile_value(&over, &registry).is_err(), "{group}.{field}");
    }
    check_expression_error(
        &format!(r#"value("t","raw")=="{}x""#, "é".repeat(512)),
        ExpressionError::String,
        &registry,
    );
    check_expression_error(
        r#"value("t","raw")=="\uD800""#,
        ExpressionError::String,
        &registry,
    );
    let long_selector = "é".repeat(512);
    let long_revision = "R".repeat(64);
    let long_registry = Registry::new(
        &long_revision,
        [&long_selector],
        [] as [&str; 0],
        [] as [(&str, &str); 0],
    )
    .unwrap();
    let mut long = request(&format!(
        r#"exists("{long_selector}") and exists(alias("a"))"#
    ));
    long["registryRevision"] = json!(long_revision);
    long["aliases"] = json!([{"name":"a","selector":long_selector}]);
    assert!(compile_value(&long, &long_registry).is_ok());
    long["aliases"][0]["selector"] = json!(format!("{long_selector}x"));
    assert!(compile_value(&long, &long_registry).is_err());
    assert!(
        Registry::new(
            "R".repeat(65),
            [&long_selector],
            [] as [&str; 0],
            [] as [(&str, &str); 0]
        )
        .is_err()
    );

    let malicious = r#"x") or exists("t") or value("t","raw")=="x"#;
    let mut data = request(r#"value(alias("a"),"raw")==param("p")"#);
    data["aliases"] = json!([{"name":"a","selector":"t"}]);
    data["parameters"] = json!([{"name":"p","type":"string","value":malicious}]);
    let mut observation = Observations::new(&registry);
    observation
        .insert(
            "t",
            SelectorObservation {
                coverage: Coverage::Complete,
                occurrences: vec![occurrence(Some(Scalar::String(malicious.into())), None)],
            },
        )
        .unwrap();
    assert_eq!(
        compile_value(&data, &registry)
            .unwrap()
            .evaluate(&observation)
            .truth,
        Truth::True
    );
    data["parameters"][0]["name"] = json!("a");
    assert_eq!(
        compile_value(&data, &registry).unwrap_err(),
        CompileError::Declaration {
            group: "parameters",
            index: 0,
            kind: DeclarationError::NameCollision
        }
    );
    data["parameters"][0]["name"] = json!("p");
    assert!(compile_value(&data, &registry).is_ok());
    data["aliases"][0]["selector"] = json!("p");
    assert!(compile_value(&data, &registry).is_err());

    for expression in [
        r#"exists("t") or file("C:/data/config.json")"#,
        r#"exists("t") or fetch("https://example.invalid/sentinel")"#,
        r#"exists("t") or env("USERPROFILE")"#,
        r#"exists("t") or spawn("powershell")"#,
        r#"exists("t") or import("external-module")"#,
        r#"exists("t") or hook("on_read")"#,
        r#"exists(alias(param("a")))"#,
    ] {
        assert!(
            compile_value(&request(expression), &registry).is_err(),
            "{expression}"
        );
    }
}

#[test]
fn batch_policies_and_independent_concurrent_lifetimes() {
    let registry = registry();
    let compiled = filter(r#"exists("t")"#, &registry);
    let selected = truth_observations(&registry);
    let unknown = Observations::new(&registry);
    let mut excluded = Observations::new(&registry);
    excluded
        .insert("t", observation(Coverage::Complete, vec![]))
        .unwrap();
    for (policy, status, ordinals) in [
        (UnknownPolicy::default(), BatchStatus::Failed, vec![]),
        (UnknownPolicy::Continue, BatchStatus::Partial, vec![1, 3]),
    ] {
        let batch = compiled.evaluate_batch([&unknown, &selected, &excluded, &selected], policy);
        assert_eq!(batch.status, status);
        assert_eq!(batch.selected, ordinals);
        assert_eq!(
            batch
                .evaluations
                .iter()
                .map(|item| item.truth)
                .collect::<Vec<_>>(),
            [Truth::Unknown, Truth::True, Truth::False, Truth::True]
        );
    }
    assert_eq!(
        compiled
            .evaluate_batch([&excluded, &unknown], UnknownPolicy::Continue)
            .status,
        BatchStatus::Failed
    );
    assert_eq!(
        compiled
            .evaluate_batch([&excluded, &selected], UnknownPolicy::Fail)
            .status,
        BatchStatus::Complete
    );
    let unrelated = Registry::new(
        "authored-v1",
        ["t"],
        [] as [&str; 0],
        [] as [(&str, &str); 0],
    )
    .unwrap();
    assert_eq!(
        compiled.evaluate(&Observations::new(&unrelated)).issues[0].kind,
        IssueKind::RegistryMismatch
    );

    std::thread::scope(|scope| {
        for index in 0..8 {
            let (registry, compiled, selected) = (&registry, &compiled, &selected);
            scope.spawn(move || {
                let mut request = request(r#"exists(alias("a")) and value("t","raw")==param("p")"#);
                request["aliases"] = json!([{"name":"a","selector":"t"}]);
                request["parameters"] = json!([{"name":"p","type":"integer","value":index}]);
                let local = compile_value(&request, registry).unwrap();
                drop(request);
                let mut observed = Observations::new(registry);
                observed
                    .insert(
                        "t",
                        observation(
                            Coverage::Complete,
                            vec![occurrence(
                                Some(Scalar::Number(
                                    ExactNumber::from_rational(index, 1).unwrap(),
                                )),
                                None,
                            )],
                        ),
                    )
                    .unwrap();
                for _ in 0..20 {
                    assert_eq!(local.evaluate(&observed).truth, Truth::True);
                    assert_eq!(compiled.evaluate(selected).truth, Truth::True);
                }
            });
        }
    });
}
