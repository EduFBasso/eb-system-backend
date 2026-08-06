# Seed data for the approved dynamic podology workflow.
# General anamnesis remains fixed/structured in the client serializer.
# Used by: python manage.py seed_anamnesis --professional-email=<email>

SECTORS = [
    {
        'sector': 'Calçados',
        'sector_order': 0,
        'fields': [
            {
                'code': 'footwear_used',
                'label': 'Calçado usado',
                'field_type': 'radio',
                'options': [
                    'Sapato baixo',
                    'Tênis',
                    'Chinelo',
                    'Sandália',
                    'Salto alto',
                    'Outros',
                ],
                'order': 0,
            },
            {
                'code': 'footwear_used_other',
                'label': 'Qual calçado?',
                'field_type': 'text',
                'options': None,
                'placeholder': 'Descreva o calçado...',
                'depends_on': 'footwear_used',
                'show_when_value': 'Outros',
                'order': 1,
            },
            {
                'code': 'sock_used',
                'label': 'Meia usada',
                'field_type': 'radio',
                'options': ['Algodão', 'Sintética', 'Compressão', 'Sem meia'],
                'order': 2,
            },
        ],
    },
    {
        'sector': 'Condições de sensibilidade',
        'sector_order': 1,
        'fields': [
            {
                'code': 'sensitivity_test',
                'label': 'Condições de sensibilidade',
                'field_type': 'radio',
                'options': ['Normal', 'Alterado', 'Não avaliado', 'Outros'],
                'order': 0,
            },
            {
                'code': 'sensitivity_test_other',
                'label': 'Qual condição?',
                'field_type': 'text',
                'options': None,
                'placeholder': 'Descreva a condição...',
                'depends_on': 'sensitivity_test',
                'show_when_value': 'Outros',
                'order': 1,
            },
        ],
    },
    {
        'sector': 'Alterações ungueais esquerda',
        'sector_order': 2,
        'fields': [
            {
                'code': 'nail_changes_left',
                'label': 'Alterações ungueais esquerda',
                'field_type': 'radio',
                'selection_mode': 'multiple',
                'options': [
                    'onicofose',
                    'onicocriptose',
                    'onicomicose',
                    'paroniquia',
                    'onicocrifose',
                    'Outros',
                ],
                'order': 0,
            },
            {
                'code': 'nail_changes_left_other',
                'label': 'Outra alteração esquerda',
                'field_type': 'text',
                'options': None,
                'placeholder': 'Descreva outra alteração...',
                'depends_on': 'nail_changes_left',
                'show_when_value': 'Outros',
                'order': 1,
            },
        ],
    },
    {
        'sector': 'Alterações ungueais direita',
        'sector_order': 3,
        'fields': [
            {
                'code': 'nail_changes_right',
                'label': 'Alterações ungueais direita',
                'field_type': 'radio',
                'selection_mode': 'multiple',
                'options': [
                    'onicofose',
                    'onicocriptose',
                    'onicomicose',
                    'paroniquia',
                    'onicocrifose',
                    'Outros',
                ],
                'order': 0,
            },
            {
                'code': 'nail_changes_right_other',
                'label': 'Outra alteração direita',
                'field_type': 'text',
                'options': None,
                'placeholder': 'Descreva outra alteração...',
                'depends_on': 'nail_changes_right',
                'show_when_value': 'Outros',
                'order': 1,
            },
        ],
    },
    {
        'sector': 'Observações',
        'sector_order': 4,
        'fields': [
            {
                'code': 'other_procedures',
                'label': 'Outros procedimentos',
                'field_type': 'textarea',
                'options': None,
                'order': 0,
            },
        ],
    },
]
