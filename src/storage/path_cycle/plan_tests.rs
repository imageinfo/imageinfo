use super::*;

#[test]
fn exact_existing_0097_steps_and_prefixes() {
    let spec: serde_json::Value = serde_json::from_str(include_str!(
        "../../../docs/write-safety/two-name-cycle.v1.json"
    ))
    .unwrap();
    let names = ["a", "b", "temp"];
    let objects = ["alpha", "beta"];
    for (index, &(original, source, target)) in MOVES.iter().enumerate() {
        assert_eq!(spec["moves"][index]["source"], names[source]);
        assert_eq!(spec["moves"][index]["target"], names[target]);
        assert_eq!(spec["moves"][index]["object"], objects[original]);
    }
    for (index, key) in ["initial", "after_first", "after_second", "complete"]
        .iter()
        .enumerate()
    {
        for (slot, name) in names.iter().enumerate() {
            let expected = match spec["states"][key][name].as_str() {
                Some("alpha") => Binding::Alpha,
                Some("beta") => Binding::Beta,
                None => Binding::Absent,
                _ => panic!("unrecognized accepted state"),
            };
            assert_eq!(PREFIXES[index][slot], expected);
        }
    }
}

#[test]
fn explicit_names_are_distinct_bounded_ordinary_same_parent() {
    let parent = Path::new("scope");
    assert!(
        Plan::new(
            parent.join("a.bin"),
            parent.join("b.bin"),
            parent.join("tmp.bin")
        )
        .is_ok()
    );
    for temp in [
        "a.bin",
        "A.BIN",
        "b.BIN",
        "CON",
        "nul.txt",
        "LPT1.bin",
        "bad:stream",
        "bad.",
        "bad ",
        "x/y",
        "\u{e9}",
    ] {
        assert!(
            Plan::new(
                parent.join("a.bin"),
                parent.join("b.bin"),
                parent.join(temp)
            )
            .is_err(),
            "{temp}"
        );
    }
    assert!(
        Plan::new(
            parent.join("a.bin"),
            PathBuf::from("other/b.bin"),
            parent.join("tmp.bin")
        )
        .is_err()
    );
    assert!(
        Plan::new(
            PathBuf::from("a"),
            PathBuf::from("b"),
            PathBuf::from("temp")
        )
        .is_err()
    );
    assert!(
        Plan::new(
            parent.join("a.bin"),
            parent.join("b.bin"),
            parent.join("x".repeat(101))
        )
        .is_err()
    );
}
