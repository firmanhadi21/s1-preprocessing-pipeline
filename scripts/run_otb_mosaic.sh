#!/bin/bash
# OTB Mosaic script for Java Island

source /home/unika_sianturi/work/OTB/otbenv.profile

echo "OTB Environment loaded"
echo "Creating seamless mosaic with OTB..."

mkdir -p workspace_java/mosaic/tmp

otbcli_Mosaic \
    -il \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240102T104957_20240102T105026_051926_064619_8BBA_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240102T105026_20240102T105051_051926_064619_BB52_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240102T105051_20240102T105116_051926_064619_BDA9_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240103T221740_20240103T221805_051948_0646E2_013D_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240103T221805_20240103T221830_051948_0646E2_6352_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240105T111509_20240105T111538_051970_0647AB_30A9_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240105T111538_20240105T111603_051970_0647AB_7605_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240105T220056_20240105T220121_051977_0647E8_F1D8_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240105T220121_20240105T220146_051977_0647E8_CEF0_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240105T220146_20240105T220211_051977_0647E8_10CE_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240107T105825_20240107T105854_051999_0648AD_9018_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240107T105854_20240107T105922_051999_0648AD_834B_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240108T222532_20240108T222557_052021_06495A_6340_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240108T222557_20240108T222622_052021_06495A_A229_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240108T222622_20240108T222650_052021_06495A_191C_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240109T104147_20240109T104216_052028_06499E_1E1F_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240109T104216_20240109T104244_052028_06499E_20C4_processed_VH.tif \
    workspace_java/geotiff/S1A_IW_GRDH_1SDV_20240110T112334_20240110T112403_052043_064A27_AE53_processed_VH.tif \
    -out workspace_java/mosaic/S1_Java_mosaic_otb.tif float \
    -comp.feather large \
    -harmo.method band \
    -harmo.cost rmse \
    -nodata -32768 \
    -tmpdir workspace_java/mosaic/tmp \
    -ram 16000

echo "Mosaic complete!"
rm -rf workspace_java/mosaic/tmp
