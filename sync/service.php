<?php

$STORE_URL = $_ENV['STORE_URL'];
$WEBSERVICE_KEY = $_ENV['WEBSERVICE_KEY'];

$webService = new PrestaShopWebservice($STORE_URL, $WEBSERVICE_KEY, false);

function getBlankSchema($resource)
{
    global $webService, $STORE_URL;

    $opt = [
        'url' => $STORE_URL . "/api/$resource?schema=blank"
    ];

    $result = $webService->get($opt);

    return $result;
}

function getManufacturerByName($manufacturerName)
{
    global $webService;

    $opt = [
        'resource' => 'manufacturers',
        'filter[name]' => "[$manufacturerName]",
    ];

    $result = $webService->get($opt);

    return $result->manufacturers->manufacturer['id'];
};

function addManufacturer($manufacturerName)
{
    global $webService;

    $blankXml = getBlankSchema('manufacturers');
    $blankXml->manufacturer->name = $manufacturerName;

    $blankXml->manufacturer->active = 1;

    $opt = [
        'resource' => 'manufacturers',
        'postXml' => $blankXml->asXML()
    ];

    $result = $webService->add($opt);

    return $result->manufacturer->id;
}

function getProductByReference($reference)
{
    global $webService;

    $opt = [
        'resource' => 'products',
        'filter[reference]' => "[$reference]"
    ];

    $result = $webService->get($opt);

    return $result->products->product['id'];
};

function addProduct(
    $reference,
    $manufacturerId,
    $name,
    $weight,
    $retail_price,
    $description,
    $meta_tile,
    $meta_description
) {
    global $webService;

    $blankXml = getBlankSchema('products');
    $blankXml->product->reference = $reference;
    $blankXml->product->id_manufacturer = $manufacturerId;
    $blankXml->product->name = $name;
    $blankXml->product->weight = $weight;
    $blankXml->product->price = $retail_price;
    $blankXml->product->description = $description;
    $blankXml->product->meta_title = $meta_tile;
    $blankXml->product->meta_description = $meta_description;

    $blankXml->product->show_price = 1;
    $blankXml->product->active = 1;

    $opt = [
        'resource' => 'products',
        'postXml' => $blankXml->asXML()
    ];

    $result = $webService->add($opt);

    return $result->product->id;
}

function getImageByProductId($productId)
{
    global $webService, $STORE_URL;

    $opt = [
        'url' => $STORE_URL . "/api/images/products/$productId"
    ];

    try {
        $result = $webService->get($opt);
        return $result->image->declination['id'];
    } catch (Exception $ex) {
        return null;
    }
}

function addImageToProduct($imgUrl, $productId)
{
    global $STORE_URL, $WEBSERVICE_KEY;

    $imageUrlSplit = explode('/', $imgUrl);
    $imageName = $imageUrlSplit[count($imageUrlSplit) - 1];

    $image = file_get_contents($imgUrl);
    file_put_contents($imageName, $image);

    $imageNameSplit = explode('.', $imageName);
    $imageMime = 'image/' . $imageNameSplit[count($imageNameSplit) - 1];

    $args['image'] = new CURLFile($imageName, $imageMime);
    $urlImage = $STORE_URL . "/api/images/products/$productId/";

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_HEADER, 1);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLINFO_HEADER_OUT, 1);
    curl_setopt($ch, CURLOPT_URL, $urlImage);
    curl_setopt($ch, CURLOPT_POST, 1);
    curl_setopt($ch, CURLOPT_USERPWD, $WEBSERVICE_KEY . ':');
    curl_setopt($ch, CURLOPT_POSTFIELDS, $args);
    curl_exec($ch);
    curl_close($ch);

    unlink($imageName);
}
