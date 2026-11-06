from pathlib import Path
from unittest.mock import patch
import pytest
import smart_operator as operator

def test_predictive_generation_never_falls_back_to_random(tmp_path):
    lifecycle = {'target_contest': 3081, 'state': 'ADJUDICATED'}
    with patch.object(operator, 'canonical_root', return_value=tmp_path), patch.object(operator, 'load_lifecycle', return_value=lifecycle), patch('smart_contingency_card.generate_contingency_card', side_effect=AssertionError('random fallback executed')):
        with pytest.raises(ValueError, match='PREDICTIVE_CARD_BLOCKED: target=3082'):
            operator.generate_card_operation(tmp_path, 3082)
    assert not (tmp_path / 'runtime' / 'contingency_cards').exists()

@pytest.mark.parametrize('state', ['FROZEN', 'ADJUDICATED', 'REVIEWED'])
def test_no_silent_substitution_for_unfinished_prior_cycle(tmp_path, state):
    with patch.object(operator, 'canonical_root', return_value=tmp_path), patch.object(operator, 'load_lifecycle', return_value={'target_contest': 3081, 'state': state}):
        with pytest.raises(ValueError, match='PREDICTIVE_CARD_BLOCKED'):
            operator.generate_card_operation(tmp_path, 3082)

def test_prepared_target_runs_model_path(tmp_path):
    with patch.object(operator, 'canonical_root', return_value=tmp_path), patch.object(operator, 'load_lifecycle', return_value={'target_contest': 3082, 'state': 'PREPARED'}), patch.object(operator, 'authorize_generation_operation') as auth, patch.object(operator, 'freeze_operation', return_value={'status':'FROZEN','target_contest':3082,'model_certified':True}) as freeze:
        result = operator.generate_card_operation(tmp_path, 3082)
    assert result['status'] == 'FROZEN'
    auth.assert_called_once_with(tmp_path, 3082)
    freeze.assert_called_once_with(tmp_path, 3082)
