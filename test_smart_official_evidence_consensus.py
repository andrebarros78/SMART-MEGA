from datetime import datetime

import pandas as pd
import pytest

import smart_official_evidence_consensus as consensus


def payload(target=3054, numbers=None, date="05/09/2026"):
    return {
        "numero": target,
        "dataApuracao": date,
        "listaDezenas": [f"{n:02d}" for n in (numbers or [1, 2, 3, 4, 5, 6])],
        "acumulado": False,
    }


def frame(rows):
    data=[]
    for contest,date,numbers in rows:
        row={"Concurso":contest,"Data do Sorteio":datetime.strptime(date,"%d/%m/%Y")}
        row.update({f"Bola{i}":number for i,number in enumerate(numbers,1)})
        data.append(row)
    return pd.DataFrame(data)


def test_dual_caixa_channels_must_agree_before_source_corroboration_authority():
    secondary=frame([(3054,"05/09/2026",[1,2,3,4,5,6])])
    result=consensus.corroborate(payload(),3054,secondary_frame=secondary)
    assert result["status"]=="DUAL_CAIXA_CHANNEL_CONSENSUS"
    assert result["operational_adjudication_authorized"] is True
    assert result["dual_channel_corroborated"] is True
    assert result["terminal_source_corroboration_authorized"] is True
    assert result["independent_audit_still_required_for_terminal_6of6"] is True
    assert result["terminal_6of6_proven"] is False


def test_stale_official_download_does_not_block_operational_api_but_blocks_terminal_corroboration():
    secondary=frame([(2964,"01/01/2026",[7,8,9,10,11,12])])
    result=consensus.corroborate(payload(),3054,secondary_frame=secondary)
    assert result["status"]=="PRIMARY_CAIXA_API_VALID_SECONDARY_DOWNLOAD_STALE"
    assert result["secondary"]["max_contest"]==2964
    assert result["operational_adjudication_authorized"] is True
    assert result["dual_channel_corroborated"] is False
    assert result["terminal_source_corroboration_authorized"] is False


def test_unavailable_secondary_is_explicit_and_never_fake_consensus():
    result=consensus.corroborate(payload(),3054,secondary_error="timeout")
    assert result["status"]=="PRIMARY_CAIXA_API_VALID_SECONDARY_UNAVAILABLE"
    assert result["secondary"] is None
    assert result["secondary_error"]=="timeout"
    assert result["terminal_source_corroboration_authorized"] is False


def test_channel_conflict_is_fatal():
    secondary=frame([(3054,"05/09/2026",[1,2,3,4,5,7])])
    with pytest.raises(ValueError,match="disagree on drawn numbers"):
        consensus.corroborate(payload(),3054,secondary_frame=secondary)


def test_secondary_date_conflict_is_fatal():
    secondary=frame([(3054,"06/09/2026",[1,2,3,4,5,6])])
    with pytest.raises(ValueError,match="disagree on draw date"):
        consensus.corroborate(payload(),3054,secondary_frame=secondary)


def test_download_reaching_target_range_without_unique_target_is_rejected():
    secondary=frame([(3055,"06/09/2026",[1,2,3,4,5,6])])
    with pytest.raises(ValueError,match="target is not unique"):
        consensus.observe_download_frame(secondary,3054)
