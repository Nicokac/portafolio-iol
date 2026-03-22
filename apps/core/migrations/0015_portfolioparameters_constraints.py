from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_iolmarketsnapshotobservation'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='portfolioparameters',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    liquidez_target__gte=0,
                    liquidez_target__lte=100,
                    usa_target__gte=0,
                    usa_target__lte=100,
                    argentina_target__gte=0,
                    argentina_target__lte=100,
                    emerging_target__gte=0,
                    emerging_target__lte=100,
                ),
                name='portfolio_params_target_range_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='portfolioparameters',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    max_single_position__gte=0,
                    max_single_position__lte=100,
                    risk_free_rate__gte=-100,
                    risk_free_rate__lte=100,
                    rebalance_threshold__gte=0,
                    rebalance_threshold__lte=100,
                ),
                name='portfolio_params_risk_range_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='portfolioparameters',
            constraint=models.CheckConstraint(
                condition=models.expressions.RawSQL(
                    '(liquidez_target + usa_target + argentina_target + emerging_target) = 100',
                    params=[],
                    output_field=models.BooleanField(),
                ),
                name='portfolio_params_target_allocation_100',
            ),
        ),
    ]
