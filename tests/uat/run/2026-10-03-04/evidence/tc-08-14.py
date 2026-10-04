from tc08lib import *  # noqa


def flip(ch):
    return "B" if ch != "B" else "C"


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0814")
    pr = await preview(m, doc, "feature_pad", PAD30)
    tok = token(pr)
    await frame_shot(m, doc, "tc-08-14-before.png")
    head, sig = tok[len("fcb-preview:"):].split(".")
    tampered = "fcb-preview:" + head + "." + flip(sig[0]) + sig[1:]
    truncated = "fcb-preview:" + head[: len(head) // 2] + "." + sig
    variants = [("no-prefix", "not-a-token"), ("no-separator", "fcb-preview:onlybody"), ("empty-body", "fcb-preview:.sig"),
                ("empty-signature", "fcb-preview:body."), ("undecodable", "fcb-preview:!!!!.!!!!"), ("tampered-signature", tampered),
                ("truncated-body", truncated), ("non-string", 12345)]
    res = {}
    for tag, v in variants:
        r = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": v})
        res[tag] = {"status": r.get("status"), "message": msg(r)[:300]}
    log.write({"variants": res})
    for tag in res:
        print(tag, res[tag])
    log.check("not-a-token -> 'confirm.preview_id is not a preview token'",
              res["no-prefix"]["message"] == "confirm.preview_id is not a preview token", res["no-prefix"])
    mal = [res[t]["message"] for t in ("no-separator", "empty-body", "empty-signature")]
    log.check("onlybody / .sig / body. -> 'confirm.preview_id is malformed'", all(x == "confirm.preview_id is malformed" for x in mal), mal)
    log.check("!!!!.!!!! -> 'confirm.preview_id is not decodable'",
              res["undecodable"]["message"] == "confirm.preview_id is not decodable", res["undecodable"])
    log.check("tampered signature -> 'confirm.preview_id carries an invalid signature'",
              res["tampered-signature"]["message"] == "confirm.preview_id carries an invalid signature", res["tampered-signature"])
    four = {res["no-prefix"]["message"], res["no-separator"]["message"], res["undecodable"]["message"],
            res["tampered-signature"]["message"]}
    log.check("the four messages are four different strings", len(four) == 4, sorted(four))
    log.check("payload missing a field -> 'confirm.preview_id payload is missing [...]'",
              res["truncated-body"]["message"].startswith("confirm.preview_id payload is missing "),
              {"truncated_body_result": res["truncated-body"],
               "note": "a payload lacking a field needs a re-signed token; the secret is per-process, so the TC's own "
                       "substitute (truncated body) can only fail the signature check"})
    log.check("non-string preview_id 12345 refused ('is not a preview token' or schema reject)",
              res["non-string"]["status"] != "OK", res["non-string"])
    tr = await names(m, doc)
    log.check("no Pad after all variants", "Pad" not in tr, tr)
    await frame_shot(m, doc, "tc-08-14-after.png")
    print("DOC", doc)


go("tc-08-14", body)
