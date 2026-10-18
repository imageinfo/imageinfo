use super::*;

#[test]
fn exact_preview_is_one_or_two_moves() {
    let ordinary = RenamePlan::new(
        Path::new("root/old.marker"),
        Path::new("root/new.marker"),
        None,
    )
    .unwrap();
    assert_eq!(ordinary.steps(), [Path::new("root/new.marker")]);
    let case = RenamePlan::new(
        Path::new("root/old.marker"),
        Path::new("root/OLD.marker"),
        Some(Path::new("root/previewed.tmp")),
    )
    .unwrap();
    assert_eq!(
        case.steps(),
        [
            Path::new("root/previewed.tmp"),
            Path::new("root/OLD.marker")
        ]
    );
}

#[test]
fn preview_refuses_aliases_and_unbounded_names() {
    let old = Path::new("root/old.marker");
    let case = Path::new("root/OLD.marker");
    assert_eq!(
        RenamePlan::new(old, case, None),
        Err(PlanError::TemporaryRequired)
    );
    assert_eq!(
        RenamePlan::new(old, case, Some(old)),
        Err(PlanError::TemporaryAlias)
    );
    assert_eq!(RenamePlan::new(old, old, None), Err(PlanError::Unchanged));
    assert_eq!(
        RenamePlan::new(old, Path::new("other/new"), None),
        Err(PlanError::DifferentParent)
    );
    for invalid in [
        "root/NUL.txt",
        "root/new.",
        "root/nonasciié",
        "root/stream:ads",
        "root/LPT1",
    ] {
        assert_eq!(
            RenamePlan::new(old, Path::new(invalid), None),
            Err(PlanError::UnsupportedName)
        );
    }
    assert_eq!(
        RenamePlan::new(old, Path::new("root/new"), Some(Path::new("root/temp"))),
        Err(PlanError::UnexpectedTemporary)
    );
}
