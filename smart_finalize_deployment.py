from __future__ import annotations
import hashlib,json,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
import smart_continuity_consolidator as cc

SCHEMA='SMART_IMPLEMENTATION_PROOF_20260904_V1'
JUNIT='SMART_AUDIT_JUNIT_DEPLOYMENT_20260904.xml'

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()

def read(path:Path)->dict[str,Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))

def junit_summary(path:Path)->dict[str,Any]:
    root=ET.parse(path).getroot()
    if root.tag=='testsuites':
        tests=int(root.attrib.get('tests',0)); failures=int(root.attrib.get('failures',0)); errors=int(root.attrib.get('errors',0)); skipped=int(root.attrib.get('skipped',0)); duration=float(root.attrib.get('time',0.0))
        if tests==0:
            suites=list(root.findall('testsuite'))
            tests=sum(int(x.attrib.get('tests',0)) for x in suites); failures=sum(int(x.attrib.get('failures',0)) for x in suites); errors=sum(int(x.attrib.get('errors',0)) for x in suites); skipped=sum(int(x.attrib.get('skipped',0)) for x in suites); duration=sum(float(x.attrib.get('time',0.0)) for x in suites)
    else:
        tests=int(root.attrib.get('tests',0)); failures=int(root.attrib.get('failures',0)); errors=int(root.attrib.get('errors',0)); skipped=int(root.attrib.get('skipped',0)); duration=float(root.attrib.get('time',0.0))
    return {'tests':tests,'failures':failures,'errors':errors,'skipped':skipped,'time_seconds':duration,'status':'PASS' if failures==0 and errors==0 else 'FAIL','sha256':sha(path),'file':path.name}

def build(root:Path)->dict[str,Any]:
    consolidation=cc.write(root)
    mission=read(root/'SMART_MISSION_STATUS.json')
    orchestration=read(root/'SMART_AGENT_SKILL_ORCHESTRATION.json')
    p1p2=read(root/'SMART_P1_P2_CARTOGRAPHY_PROOF.json')
    conv=read(root/'SMART_MONTE_CARLO_CONVERGENCE_1000.json')
    powered=read(root/'SMART_FALSIFICATION_REPORT_POWERED.json')
    junit=junit_summary(root/JUNIT)
    freeze=root/'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json'
    data=root/'Mega-Sena_through_3053_v2.xlsx'
    agents=orchestration.get('agents',{})
    checks={
      'final_regression_pass':junit['status']=='PASS',
      'freeze_3054_immutable':sha(freeze)==cc.FREEZE_EXPECTED_SHA256,
      'dataset_3053_bound':sha(data)==cc.DATA_EXPECTED_SHA256,
      'agent_skill_orchestration_pass':orchestration.get('integration_status')=='PASS',
      'all_agents_non_authoritative':bool(agents) and all(not bool(a.get('terminal_authority')) and not bool(a.get('predictive_weight_authorized')) and not bool(a.get('freeze_mutation_authorized')) for a in agents.values()),
      'p1p2_canonical_1000':int(p1p2.get('replications',0))==1000 and p1p2.get('p2_atlas_sha256')==sha(root/'SMART_RANDOMNESS_ATLAS.json'),
      'convergence_audited_1000':int(conv.get('final_replications',0))==1000 and conv.get('final_atlas_sha256')==sha(root/'SMART_RANDOMNESS_ATLAS_1000.json'),
      'powered_holm_resolution_sufficient':powered['multiplicity']['resolution_sufficient'] is True,
      'powered_controls_detected':powered['adversarial_sensitivity']['all_expected_directions_detected'] is True,
      'no_new_predictive_weight_authorized':powered['predictive_weight_authorized'] is False and p1p2.get('predictive_weight_authorized') is False and conv.get('predictive_weight_authorized') is False,
      'chat_consolidation_pass':consolidation.get('consolidation_status')=='PASS',
      'mission_not_false_proven':mission.get('status')=='MISSION_ACTIVE' and mission.get('terminal_6of6_proven') is False,
    }
    proof={
      'schema':SCHEMA,'generated_at_utc':datetime.now(timezone.utc).isoformat(),
      'scope':'unified chat continuity, agent/skill orchestration, powered falsification, optimized 1000-replication cartography, convergence audit and canonical promotion',
      'deployment_status':'PASS' if all(checks.values()) else 'FAIL',
      'workspace':str(root),'branch':'master',
      'test_evidence':junit,
      'freeze_3054':{'top6':[10,11,27,30,35,38],'sha256':sha(freeze),'immutable':sha(freeze)==cc.FREEZE_EXPECTED_SHA256},
      'agent_skill_orchestration':{'unique_capabilities_total':orchestration['inventory']['unique_capabilities_total'],'agent_count':len(agents),'status':orchestration['integration_status'],'artifact_sha256':sha(root/'SMART_AGENT_SKILL_ORCHESTRATION.json')},
      'powered_falsification':{'replications':powered['replications'],'holm_family_size':powered['multiplicity']['family_size'],'minimum_replications':powered['multiplicity']['minimum_replications_for_resolution'],'resolution_sufficient':powered['multiplicity']['resolution_sufficient'],'holm_rejections':powered['multiplicity']['rejected_comparisons'],'controls_detected':powered['adversarial_sensitivity']['all_expected_directions_detected'],'predictive_weight_authorized':powered['predictive_weight_authorized'],'artifact_sha256':sha(root/'SMART_FALSIFICATION_REPORT_POWERED.json')},
      'cartography_1000':{'replications':p1p2['replications'],'canonical_atlas_sha256':p1p2['p2_atlas_sha256'],'canonical_manifest_sha256':p1p2['p1_manifest_sha256'],'proof_sha256':sha(root/'SMART_P1_P2_CARTOGRAPHY_PROOF.json')},
      'convergence':{'summary':conv['stability_summary'],'artifact_sha256':sha(root/'SMART_MONTE_CARLO_CONVERGENCE_1000.json')},
      'checks':checks,
      'mission_state':mission['status'],'terminal_6of6_proven':mission['terminal_6of6_proven'],
      'scientific_predictive_status':mission.get('scientific_predictive_status'),
      'prospective_advantage_status':mission.get('prospective_advantage_status'),
    }
    return proof

def write(root:Path)->dict[str,Any]:
    proof=build(root)
    if proof['deployment_status']!='PASS': raise RuntimeError({'deployment_checks':proof['checks']})
    (root/'SMART_IMPLEMENTATION_PROOF_20260904.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    j=proof['test_evidence']; c=proof['convergence']['summary']; f=proof['powered_falsification']; a=proof['agent_skill_orchestration']
    md=f'''# SMART-MEGA â€” CONTINUIDADE CANÃ”NICA\n\n**AtualizaÃ§Ã£o:** {proof['generated_at_utc']}\n**Workspace:** `C:\\New Projet\\SMART-MEGA`\n**Branch:** `master`\n**Estado soberano:** `MISSION_ACTIVE`\n\n## ImplantaÃ§Ã£o consolidada\n\nOs dois estados de continuidade de 04/09/2026 foram unificados em `SMART_CHAT_CONSOLIDATION_20260904.json`, sempre subordinados Ã  evidÃªncia real do repositÃ³rio. A integraÃ§Ã£o de agentes e skills estÃ¡ materializada em `SMART_AGENT_SKILL_ORCHESTRATION.json`.\n\n- capacidades reconciliadas: **{a['unique_capabilities_total']}**;\n- agentes canÃ´nicos: **{a['agent_count']}**;\n- cÃ³digo externo: quarentena/source-only, sem autoexecuÃ§Ã£o;\n- autoridade direta para pesos: **nenhuma**;\n- autoridade para alterar freeze: **nenhuma**;\n- autoridade terminal de agentes: **nenhuma**.\n\n## Freeze prospectiva 3054\n\n`10 - 11 - 27 - 30 - 35 - 38`\n\nSHA-256: `{proof['freeze_3054']['sha256']}`\n\nA freeze permaneceu imutÃ¡vel durante toda a implantaÃ§Ã£o.\n\n## P1/P2 â€” cartografia canÃ´nica\n\nOs universos U0â€“U6 e o atlas canÃ´nico foram promovidos para **1.000 rÃ©plicas**, vinculados ao dataset atÃ© o concurso 3053. A promoÃ§Ã£o ocorreu somente apÃ³s auditoria de integridade e convergÃªncia.\n\nConvergÃªncia 200 â†’ 1000, excluindo nulos degenerados dos agregados de p:\n\n- mÃ¡ximo |Î”p|: **{c['max_p_abs_delta_vs_1000']:.6f}**;\n- mediana |Î”p|: **{c['median_p_abs_delta_vs_1000']:.6f}**;\n- mÃ¡ximo deslocamento da mÃ©dia em desvios-padrÃ£o nulos finais: **{c['max_mean_delta_in_final_null_sd_vs_1000']:.6f}**;\n- mÃ©tricas nulas degeneradas auditadas separadamente: **{c['degenerate_metric_count']}**;\n- maior diferenÃ§a absoluta de mÃ©dia entre degeneradas: **{c['max_degenerate_mean_abs_delta']:.3e}**.\n\nEsses nÃºmeros sÃ£o diagnÃ³stico de Monte Carlo, nÃ£o autorizaÃ§Ã£o preditiva.\n\n## FalsificaÃ§Ã£o com poder suficiente\n\n- rÃ©plicas: **{f['replications']}**;\n- famÃ­lia Holm: **{f['holm_family_size']}** comparaÃ§Ãµes;\n- mÃ­nimo necessÃ¡rio para resoluÃ§Ã£o declarada: **{f['minimum_replications']}**;\n- resoluÃ§Ã£o suficiente: **{str(f['resolution_sufficient']).lower()}**;\n- rejeiÃ§Ãµes Holm: **{len(f['holm_rejections'])}**;\n- controles adversariais esperados detectados: **{str(f['controls_detected']).lower()}**;\n- novo peso preditivo autorizado: **nÃ£o**.\n\n## RegressÃ£o final da implantaÃ§Ã£o\n\n`{j['tests']} passed / {j['failures']} failures / {j['errors']} errors`\n\nJUnit: `{j['file']}`\nSHA-256: `{j['sha256']}`\n\n## Regra de continuidade\n\nA engenharia desta implantaÃ§Ã£o estÃ¡ comprovada, mas isso **nÃ£o** satisfaz o critÃ©rio cientÃ­fico terminal 6/6. O prÃ³ximo gate empÃ­rico soberano permanece a adjudicaÃ§Ã£o prospectiva do concurso 3054 contra a freeze jÃ¡ registrada. Pesquisa shadow pode continuar, sem modificar retroativamente a previsÃ£o 3054 e sem promover sinais sem nova evidÃªncia vÃ¡lida.\n\n**Estado terminal:** `terminal_6of6_proven = false`\n**MissÃ£o:** `MISSION_ACTIVE`\n'''
    (root/'SMART_CONTINUITY.md').write_text(md,encoding='utf-8')
    return proof

if __name__=='__main__':
    import sys
    root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
    p=write(root)
    print(json.dumps({'deployment_status':p['deployment_status'],'tests':p['test_evidence']['tests'],'failures':p['test_evidence']['failures'],'mission_state':p['mission_state'],'terminal_6of6_proven':p['terminal_6of6_proven']}))
